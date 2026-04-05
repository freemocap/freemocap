"""
FreemocapApplication with SettingsManager integration.

"""
import logging
import multiprocessing
from dataclasses import dataclass, field

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
from skellycam.core.camera_group.camera_group import CameraGroupState
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager, get_or_create_camera_group_manager
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraGroupIdString

from freemocap.core.pipeline.posthoc.posthoc_pipeline import PosthocPipeline
from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import PosthocPipelineManager
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager
from freemocap.app.settings import SettingsManager
from freemocap.core.viz.frontend_payload import FrontendPayload
from freemocap.core.pipeline.pipeline_configs import (
    CalibrationPipelineConfig,
    MocapPipelineConfig,
    RealtimePipelineConfig,
)
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt

logger = logging.getLogger(__name__)


class WorkerState(BaseModel):
    model_config = ConfigDict(frozen=True)
    pid: int
    name: str
    alive: bool
    error: str | None = None


class AppState(BaseModel):
    model_config = ConfigDict(frozen=True)
    camera_groups: dict[CameraGroupIdString, CameraGroupState]
    workers: dict[str, WorkerState]


@dataclass
class FreemocapApplication:

    global_kill_flag: multiprocessing.Value
    worker_registry: WorkerRegistry
    realtime_pipeline_manager: RealtimePipelineManager
    posthoc_pipeline_manager: PosthocPipelineManager
    camera_group_manager: CameraGroupManager
    settings_manager: SettingsManager = field(default_factory=SettingsManager)

    @classmethod
    def create(cls, fastapi_app: FastAPI) -> "FreemocapApplication":
        global_kill_flag = fastapi_app.state.global_kill_flag
        worker_registry = fastapi_app.state.worker_registry

        return cls(
            global_kill_flag=global_kill_flag,
            worker_registry=worker_registry,
            realtime_pipeline_manager=RealtimePipelineManager(
                worker_registry=worker_registry,
            ),
            posthoc_pipeline_manager=PosthocPipelineManager(
                global_kill_flag=global_kill_flag,
                worker_registry=worker_registry,
            ),
            camera_group_manager=get_or_create_camera_group_manager(app=fastapi_app),
            settings_manager=SettingsManager(),
        )

    @property
    def should_continue(self) -> bool:
        return not self.global_kill_flag.value

    # ------------------------------------------------------------------
    # Realtime pipeline operations
    # ------------------------------------------------------------------

    async def create_or_update_realtime_pipeline(
        self,
        pipeline_config: RealtimePipelineConfig,
    ) -> RealtimePipeline:
        existing = self.realtime_pipeline_manager.get_pipeline_by_camera_ids(
            camera_ids=pipeline_config.camera_ids,
        )
        if existing is not None:
            existing.update_config(new_config=pipeline_config)
            self.settings_manager.update_from_app(self)
            return existing

        camera_group = await self.camera_group_manager.create_or_update_camera_group(
            camera_configs=pipeline_config.camera_configs,
        )
        pipeline = self.realtime_pipeline_manager.create_pipeline(
            camera_group=camera_group,
            pipeline_config=pipeline_config,
        )
        self.settings_manager.update_from_app(self)
        return pipeline

    # ------------------------------------------------------------------
    # Posthoc pipeline operations
    # ------------------------------------------------------------------

    async def create_posthoc_calibration_pipeline(
        self,
        recording_info: RecordingInfo,
        calibration_config: CalibrationPipelineConfig,
    ) -> PosthocPipeline:
        pipeline = self.posthoc_pipeline_manager.create_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=calibration_config,
        )
        self.settings_manager.update_from_app(self)
        return pipeline

    async def create_posthoc_mocap_pipeline(
        self,
        recording_info: RecordingInfo,
        mocap_config: MocapPipelineConfig,
    ) -> PosthocPipeline:
        pipeline = self.posthoc_pipeline_manager.create_mocap_pipeline(
            recording_info=recording_info,
            mocap_config=mocap_config,
        )
        self.settings_manager.update_from_app(self)
        return pipeline

    # ------------------------------------------------------------------
    # Recording orchestration
    # ------------------------------------------------------------------

    async def start_recording_all(self, recording_info: RecordingInfo) -> None:
        await self.camera_group_manager.start_recording_all_groups(
            recording_info=recording_info,
        )
        self.settings_manager.update_from_app(self)

    async def stop_recording_all(self) -> RecordingInfo | None:
        recording_infos = await self.camera_group_manager.stop_recording_all_groups()
        self.settings_manager.update_from_app(self)
        if len(recording_infos) == 0:
            logger.warning("No recordings were stopped.")
            return None
        if len(recording_infos) > 1:
            raise NotImplementedError(
                "Stopping multiple recordings at once is not supported yet."
            )
        return recording_infos[0][0]

    # ------------------------------------------------------------------
    # Frontend payloads
    # ------------------------------------------------------------------

    def get_latest_frontend_payloads(
        self,
        if_newer_than: FrameNumberInt,
    ) -> dict[PipelineIdString | CameraGroupIdString, tuple[bytes, FrontendPayload | FrameNumberInt]]:
        # Clean up completed posthoc pipelines (releases relay threads + queues)
        self.posthoc_pipeline_manager.evict_completed()

        realtime_pipelines = self.realtime_pipeline_manager.pipelines
        if len(realtime_pipelines) == 0 or all(
            not p.alive for p in realtime_pipelines.values()
        ):
            cg_payloads = self.camera_group_manager.get_latest_frontend_payloads(
                if_newer_than=if_newer_than,
            )
            return {
                camera_group_id: (payload[-1], payload[0])
                for camera_group_id, payload in cg_payloads.items()
            }

        return self.realtime_pipeline_manager.get_latest_frontend_payloads(
            if_newer_than=if_newer_than,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close_pipelines(self) -> None:
        self.realtime_pipeline_manager.shutdown()
        self.posthoc_pipeline_manager.shutdown()
        self.settings_manager.update_from_app(self)

    def pause_unpause_pipelines(self) -> None:
        self.realtime_pipeline_manager.pause_unpause_all()
        self.settings_manager.update_from_app(self)

    def close(self) -> None:
        self.global_kill_flag.value = True
        self.realtime_pipeline_manager.shutdown()
        self.posthoc_pipeline_manager.shutdown()



FREEMOCAP_APP: FreemocapApplication | None = None


def create_freemocap_app(fastapi_app: FastAPI) -> FreemocapApplication:
    global FREEMOCAP_APP
    if FREEMOCAP_APP is not None:
        raise RuntimeError("FreemocapApplication already exists!")
    FREEMOCAP_APP = FreemocapApplication.create(fastapi_app=fastapi_app)
    return FREEMOCAP_APP


def get_freemocap_app() -> FreemocapApplication:
    global FREEMOCAP_APP
    if FREEMOCAP_APP is None:
        raise RuntimeError("FreemocapApplication does not exist!")
    return FREEMOCAP_APP
