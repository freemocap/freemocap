"""
FreemocapApplication: top-level application object.

Holds both pipeline managers (realtime + posthoc) and the camera group manager.
Delegates to the appropriate manager based on the operation.
"""
import logging
import multiprocessing
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from fastapi import FastAPI
from skellycam.core.camera_group.camera_group import CameraGroupState
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager, get_or_create_camera_group_manager
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraGroupIdString

from freemocap.core.pipeline.shared.pipeline_configs import (
    CalibrationPipelineConfig,
    MocapPipelineConfig,
    RealtimePipelineConfig,
)
from freemocap.core.pipeline.shared.frontend_payload import FrontendPayload
from freemocap.core.pipeline.posthoc.posthoc_pipeline import PosthocPipeline
from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import PosthocPipelineManager
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager

from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt
from skellycam.core.ipc.process_management.process_registry import ProcessRegistry

logger = logging.getLogger(__name__)


class WorkerState(BaseModel):
    """Serializable representation of a worker process state."""
    model_config = ConfigDict(frozen=True)

    pid: int
    name: str
    alive: bool
    error: str | None = None


class AppState(BaseModel):
    """Serializable representation of the application state."""
    model_config = ConfigDict(frozen=True)

    camera_groups: dict[CameraGroupIdString, CameraGroupState]
    workers: dict[str, WorkerState]


@dataclass
class FreemocapApplication:

    global_kill_flag: multiprocessing.Value
    process_registry: ProcessRegistry
    realtime_pipeline_manager: RealtimePipelineManager
    posthoc_pipeline_manager: PosthocPipelineManager
    camera_group_manager: CameraGroupManager

    @classmethod
    def create(cls, fastapi_app: FastAPI) -> "FreemocapApplication":
        global_kill_flag = fastapi_app.state.global_kill_flag
        process_registry = fastapi_app.state.process_registry

        return cls(
            global_kill_flag=global_kill_flag,
            process_registry=process_registry,
            realtime_pipeline_manager=RealtimePipelineManager(
                process_registry=process_registry,
            ),
            posthoc_pipeline_manager=PosthocPipelineManager(
                global_kill_flag=global_kill_flag,
                process_registry=process_registry,
            ),
            camera_group_manager=get_or_create_camera_group_manager(app=fastapi_app),
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
            return existing

        camera_group = await self.camera_group_manager.create_or_update_camera_group(
            camera_configs=pipeline_config.camera_configs,
        )
        return self.realtime_pipeline_manager.create_pipeline(
            camera_group=camera_group,
            pipeline_config=pipeline_config,
        )

    # ------------------------------------------------------------------
    # Posthoc pipeline operations
    # ------------------------------------------------------------------

    async def create_posthoc_calibration_pipeline(
        self,
        recording_info: RecordingInfo,
        calibration_config: CalibrationPipelineConfig,
    ) -> PosthocPipeline:
        return self.posthoc_pipeline_manager.create_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=calibration_config,
        )

    async def create_posthoc_mocap_pipeline(
        self,
        recording_info: RecordingInfo,
        mocap_config: MocapPipelineConfig,
    ) -> PosthocPipeline:
        return self.posthoc_pipeline_manager.create_mocap_pipeline(
            recording_info=recording_info,
            mocap_config=mocap_config,
        )

    # ------------------------------------------------------------------
    # Recording orchestration
    # ------------------------------------------------------------------

    async def start_recording_all(self, recording_info: RecordingInfo) -> None:
        await self.camera_group_manager.start_recording_all_groups(
            recording_info=recording_info,
        )

    async def stop_recording_all(self) -> RecordingInfo | None:
        recording_infos = await self.camera_group_manager.stop_recording_all_groups()
        if len(recording_infos) == 0:
            logger.warning("No recordings were stopped.")
            return None
        if len(recording_infos) > 1:
            raise NotImplementedError(
                "Stopping multiple recordings at once is not supported yet."
            )
        return recording_infos[0]

    # ------------------------------------------------------------------
    # Frontend payloads
    # ------------------------------------------------------------------

    def get_latest_frontend_payloads(
        self,
        if_newer_than: FrameNumberInt,
    ) -> dict[PipelineIdString | CameraGroupIdString, tuple[bytes, FrontendPayload | FrameNumberInt]]:
        realtime_pipelines = self.realtime_pipeline_manager.pipelines
        if len(realtime_pipelines) == 0 or all(
            not p.alive for p in realtime_pipelines.values()
        ):
            # No live pipelines — fall back to raw camera group payloads
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

    def pause_unpause_pipelines(self) -> None:
        self.realtime_pipeline_manager.pause_unpause_all()

    def close(self) -> None:
        self.global_kill_flag.value = True
        self.realtime_pipeline_manager.shutdown()
        self.posthoc_pipeline_manager.shutdown()

    def to_app_state(self) -> AppState:
        return AppState.from_app(self)


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