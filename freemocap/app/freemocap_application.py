import logging
import multiprocessing
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraGroupIdString
from skellycam.core.camera_group.camera_group import CameraGroupState
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

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value,
               subprocess_registry: list[multiprocessing.Process]) -> 'FreemocApplication':
        pipeline_manager = PipelineManager(global_kill_flag=global_kill_flag,
                                           subprocess_registry=subprocess_registry,)
        return cls(global_kill_flag=global_kill_flag,
                   pipeline_shutdown_event=multiprocessing.Event(),
                   pipeline_manager=pipeline_manager,
                   )

    @property
    def should_continue(self) -> bool:
        return not self.global_kill_flag.value

    @property
    def camera_group_manager(self):
        return self.skellycam_app.camera_group_manager

    def connect_or_update_pipeline(self,
                                   pipeline_config: PipelineConfig) -> ProcessingPipeline:
        pipeline = self.pipeline_manager.create_or_update_pipeline(pipeline_config=pipeline_config)
        return pipeline

    def close_pipelines(self):
        self.pipeline_manager.close_all_pipelines()

    def pause_unpause_pipelines(self):
        self.pipeline_manager.pause_unpause_pipelines()

    def start_recording_all(self, recording_info: RecordingInfo):
        self.pipeline_manager.start_recording_all(recording_info=recording_info)

    def stop_recording_all(self):
        self.pipeline_manager.stop_recording_all()

    def get_latest_frontend_payloads(self,if_newer_than:FrameNumberInt) -> dict[PipelineIdString, tuple[bytes, FrontendPayload|None]]:
        if len(self.pipeline_manager.pipelines) == 0:
            return {}

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
