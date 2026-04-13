"""
FreemocapApplication with SettingsManager integration.

"""
import logging
import multiprocessing
from dataclasses import dataclass, field

from fastapi import FastAPI
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager, get_or_create_camera_group_manager
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.posthoc.posthoc_pipeline import PosthocPipeline
from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import PosthocPipelineManager
from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager
from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.types.type_overloads import FrameNumberInt
from freemocap.core.viz.frontend_payload import FrontendImagePacket, FrontendPayload

logger = logging.getLogger(__name__)


@dataclass
class FreemocapApplication:
    global_kill_flag: multiprocessing.Value
    worker_registry: WorkerRegistry
    realtime_pipeline_manager: RealtimePipelineManager
    posthoc_pipeline_manager: PosthocPipelineManager
    camera_group_manager: CameraGroupManager

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
        )

    @property
    def should_continue(self) -> bool:
        return not self.global_kill_flag.value

    # ------------------------------------------------------------------
    # Realtime pipeline operations
    # ------------------------------------------------------------------

    async def create_or_update_realtime_pipeline(
            self,
            camera_configs:CameraConfigs,
            pipeline_config: RealtimePipelineConfig,
    ) -> RealtimePipeline:

        for pipeline in self.realtime_pipeline_manager.pipelines.values():
            pipeline.update_config(new_config=pipeline_config)
            return pipeline

        camera_group = await self.camera_group_manager.create_or_update_camera_group(
            camera_configs=camera_configs,
        )
        pipeline = self.realtime_pipeline_manager.create_pipeline(
            camera_group=camera_group,
            pipeline_config=pipeline_config,
        )
        return pipeline

    # ------------------------------------------------------------------
    # Posthoc pipeline operations
    # ------------------------------------------------------------------

    async def create_posthoc_calibration_pipeline(
            self,
            recording_info: RecordingInfo,
            calibration_config: PosthocCalibrationPipelineConfig,
    ) -> PosthocPipeline:
        pipeline = self.posthoc_pipeline_manager.create_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=calibration_config,
        )
        return pipeline

    async def create_posthoc_mocap_pipeline(
            self,
            recording_info: RecordingInfo,
            mocap_config: PosthocMocapPipelineConfig,
    ) -> PosthocPipeline:
        pipeline = self.posthoc_pipeline_manager.create_mocap_pipeline(
            recording_info=recording_info,
            mocap_config=mocap_config,
        )
        return pipeline

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
        return recording_infos[0][0]

    # ------------------------------------------------------------------
    # Frontend payloads
    # ------------------------------------------------------------------

    def get_latest_frontend_payloads(
            self,
            if_newer_than: FrameNumberInt,
    ) -> dict[str, FrontendImagePacket]:
        self.posthoc_pipeline_manager.evict_completed()

        realtime_pipelines = self.realtime_pipeline_manager.pipelines
        active_pipelines = [p for p in realtime_pipelines.values() if p.alive]

        if not active_pipelines:
            # Camera-only path
            result = {}
            for cg_id, payload in self.camera_group_manager.get_latest_frontend_payloads(
                    if_newer_than=if_newer_than
            ).items():
                frame_number, mf_timestamp, image_bytes = payload  # unpack the known tuple shape
                result[cg_id] = FrontendImagePacket(
                    image_bytes=image_bytes,
                    multiframe_timestamp=mf_timestamp,
                    frontend_payload=FrontendPayload(camera_group_id=cg_id,frame_number=frame_number),
                )
            return result

        # Pipeline path — delegate to manager, which also returns FrontendImagePacket
        return self.realtime_pipeline_manager.get_latest_frontend_payloads(
            if_newer_than=if_newer_than
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
