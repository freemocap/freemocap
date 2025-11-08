import logging
import multiprocessing
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict
from skellycam.core.camera_group.camera_group import CameraGroupState
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraGroupIdString

from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pipeline.pipeline_manager import PipelineManager
from freemocap.core.pipeline.processing_pipeline import FrontendPayload, ProcessingPipeline, PipelineState
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
    pipelines: dict[PipelineIdString, PipelineState]
    camera_groups: dict[CameraGroupIdString, CameraGroupState]
    workers: dict[str, WorkerState]


@dataclass
class FreemocApplication:
    global_kill_flag: multiprocessing.Value
    pipeline_shutdown_event: multiprocessing.Event
    pipeline_manager: PipelineManager
    camera_group_manager: CameraGroupManager

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value,
               subprocess_registry: list[multiprocessing.Process]) -> 'FreemocApplication':

        return cls(global_kill_flag=global_kill_flag,
                   pipeline_shutdown_event=multiprocessing.Event(),
                   pipeline_manager=PipelineManager(global_kill_flag=global_kill_flag,
                                                    subprocess_registry=subprocess_registry, ),
                   camera_group_manager=CameraGroupManager(global_kill_flag=global_kill_flag,
                                                           subprocess_registry=subprocess_registry, )
                   )

    @property
    def should_continue(self) -> bool:
        return not self.global_kill_flag.value

    def create_or_update_pipeline(self,
                                  pipeline_config: PipelineConfig) -> ProcessingPipeline:
        pipeline = self.pipeline_manager.get_pipeline_by_camera_ids(
            camera_ids=pipeline_config.camera_ids)
        if pipeline is not None:
            pipeline = self.pipeline_manager.update_pipeline(pipeline_config=pipeline_config)
        else:
            camera_group = self.camera_group_manager.create_or_update_camera_group(
                camera_configs=pipeline_config.camera_configs
            )
            pipeline = self.pipeline_manager.create_pipeline(
                camera_group=camera_group,
                pipeline_config=pipeline_config)
        return pipeline

    def close_pipelines(self):
        self.pipeline_manager.close_all_pipelines()

    def pause_unpause_pipelines(self):
        self.pipeline_manager.pause_unpause_pipelines()

    def start_recording_all(self, recording_info: RecordingInfo):
        self.pipeline_manager.start_recording_all(recording_info=recording_info)

    def stop_recording_all(self):
        self.pipeline_manager.stop_recording_all()

    def get_latest_frontend_payloads(self, if_newer_than: FrameNumberInt) -> dict[
        PipelineIdString | CameraGroupIdString, tuple[bytes, FrontendPayload | None]]:
        if len(self.pipeline_manager.pipelines) == 0:
            cg_payloads = self.camera_group_manager.get_latest_frontend_payloads(if_newer_than=if_newer_than)
            cg_payloads = {camera_group_id: (payload[-1], None) for camera_group_id, payload in cg_payloads.items()}
            return cg_payloads

        return self.pipeline_manager.get_latest_frontend_payloads(if_newer_than=if_newer_than)

    def close(self):
        self.global_kill_flag.value = True
        self.pipeline_shutdown_event.set()
        self.pipeline_manager.close_all_pipelines()

    def to_app_state(self):
        return AppState.from_app(self)


FREEMOCAP_APP: FreemocApplication | None = None


def create_freemocap_app(global_kill_flag: multiprocessing.Value,
                         subprocess_registry: list[multiprocessing.Process]) -> FreemocApplication:
    global FREEMOCAP_APP
    if FREEMOCAP_APP is None:
        FREEMOCAP_APP = FreemocApplication.create(global_kill_flag=global_kill_flag,
                                                  subprocess_registry=subprocess_registry)
    else:
        raise ValueError("FreemocApp already exists!")
    return FREEMOCAP_APP


def get_freemocap_app() -> FreemocApplication:
    global FREEMOCAP_APP
    if FREEMOCAP_APP is None:
        raise ValueError("FreemocApp does not exist!")
    return FREEMOCAP_APP
