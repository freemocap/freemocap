import logging
import multiprocessing
from dataclasses import dataclass

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
from skellycam.core.camera_group.camera_group import CameraGroupState
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager, get_or_create_camera_group_manager
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraGroupIdString

from freemocap.core.pipeline.frontend_payload import FrontendPayload
from freemocap.core.pipeline.pipeline_configs import RealtimePipelineConfig
from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.posthoc_calibration_pipeline import \
    CalibrationpipelineConfig
from freemocap.core.pipeline.posthoc_pipelines.posthoc_pipeline_manager import PosthocPipelineManager
from freemocap.core.pipeline.realtime_pipeline.realtime_pipeline import RealtimeProcessingPipeline
from freemocap.core.pipeline.realtime_pipeline.realtime_pipeline_manager import RealtimePipelineManager
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt

logger = logging.getLogger(__name__)


class WorkerState(BaseModel):
    """Serializable representation of a worker process state."""
    model_config = ConfigDict(
        validate_assignment=True,
        frozen=True
    )
    pid: int
    name: str
    alive: bool
    error: str | None = None


class AppState(BaseModel):
    """Serializable representation of the application state."""
    model_config = ConfigDict(
        validate_assignment=True,
        frozen=True
    )
    # pipelines: dict[PipelineIdString, PipelineState]
    camera_groups: dict[CameraGroupIdString, CameraGroupState]
    workers: dict[str, WorkerState]


@dataclass
class FreemocApplication:
    global_kill_flag: multiprocessing.Value
    pipeline_shutdown_event: multiprocessing.Event
    realtime_pipeline_manager: RealtimePipelineManager
    posthoc_pipeline_manager: PosthocPipelineManager
    camera_group_manager: CameraGroupManager

    @classmethod
    def create(cls, fastapi_app: FastAPI) -> 'FreemocApplication':

        return cls(global_kill_flag=fastapi_app.state.global_kill_flag,
                   pipeline_shutdown_event=multiprocessing.Event(),
                   realtime_pipeline_manager=RealtimePipelineManager.from_fastapi_app(fastapi_app),
                   posthoc_pipeline_manager=PosthocPipelineManager.from_fastapi_app(fastapi_app),
                   camera_group_manager=get_or_create_camera_group_manager(app=fastapi_app)
                   )

    @property
    def should_continue(self) -> bool:
        return not self.global_kill_flag.value

    async def create_or_update_realtime_pipeline(self,
                                                 pipeline_config: RealtimePipelineConfig) -> RealtimeProcessingPipeline:
        pipeline = self.realtime_pipeline_manager.get_pipeline_by_camera_ids(
            camera_ids=pipeline_config.camera_ids)
        if pipeline is not None:
            pipeline = await self.realtime_pipeline_manager.update_realtime_pipeline(pipeline_config=pipeline_config)
        else:
            camera_group = await self.camera_group_manager.create_or_update_camera_group(
                camera_configs=pipeline_config.camera_configs
            )
            # pipeline = await self.realtime_pipeline_manager.create_realtime_pipeline(
            #     camera_group=camera_group,
            #     pipeline_config=pipeline_config)
        return pipeline

    async def create_posthoc_calibration_pipeline(self,
                                                  recording_info: RecordingInfo,
                                                  calibration_pipeline_config:CalibrationpipelineConfig) -> RealtimeProcessingPipeline:
        pipeline = await self.posthoc_pipeline_manager.create_posthoc_calibration_pipeline(
            recording_info=recording_info,
            calibration_pipeline_config=calibration_pipeline_config
        )
        return pipeline
    def close_pipelines(self):
        self.realtime_pipeline_manager.close_all_realtime_pipelines()
        self.posthoc_pipeline_manager.close_all_posthoc_pipelines()

    def pause_unpause_pipelines(self):
        self.realtime_pipeline_manager.pause_unpause_pipelines()

    async def start_recording_all(self, recording_info: RecordingInfo):
        await self.camera_group_manager.start_recording_all_groups(recording_info=recording_info)

    async def stop_recording_all(self)-> RecordingInfo| None:
        recording_infos  = await self.camera_group_manager.stop_recording_all_groups()
        if len(recording_infos) == 0:
            logger.warning(f"No recordings were stopped.")
            return None
        elif len(recording_infos) >1:
            raise NotImplementedError("Stopping multiple recordings at once is not supported yet.")
        return recording_infos[0]

    def get_latest_frontend_payloads(self, if_newer_than: FrameNumberInt) -> dict[
        PipelineIdString | CameraGroupIdString, tuple[bytes, FrontendPayload | FrameNumberInt]]:
        if len(self.realtime_pipeline_manager.realtime_pipelines) == 0 or all(
                [not p.alive for p in self.realtime_pipeline_manager.realtime_pipelines.values()]):
            # if there are no pipelines, return the latest payloads from the camera groups instead
            cg_payloads = self.camera_group_manager.get_latest_frontend_payloads(if_newer_than=if_newer_than)
            cg_payloads = {camera_group_id: (payload[-1], payload[0]) for camera_group_id, payload in cg_payloads.items()}
            return cg_payloads

        return self.realtime_pipeline_manager.get_latest_frontend_payloads(if_newer_than=if_newer_than)

    def close(self):
        self.global_kill_flag.value = True
        self.pipeline_shutdown_event.set()
        self.realtime_pipeline_manager.close_all_realtime_pipelines()

    def to_app_state(self):
        return AppState.from_app(self)

    async def create_or_update_realtime_calibration_pipeline(self, calibration_task_config: CalibrationpipelineConfig) -> RealtimeProcessingPipeline:
        pipeline = await self.realtime_pipeline_manager.create_or_update_realtime_calibration_pipeline(
            calibration_task_config=calibration_task_config
        )
        return pipeline



FREEMOCAP_APP: FreemocApplication | None = None


def create_freemocap_app(fastapi_app) -> FreemocApplication:
    global FREEMOCAP_APP
    if FREEMOCAP_APP is None:
        FREEMOCAP_APP = FreemocApplication.create(fastapi_app=fastapi_app)
    else:
        raise ValueError("FreemocApp already exists!")
    return FREEMOCAP_APP


def get_freemocap_app() -> FreemocApplication:
    global FREEMOCAP_APP
    if FREEMOCAP_APP is None:
        raise ValueError("FreemocApp does not exist!")
    return FREEMOCAP_APP
