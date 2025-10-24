import logging
import multiprocessing
from dataclasses import dataclass, field

from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.types.type_overloads import CameraGroupIdString
from skellycam.skellycam_app.skellycam_app import SkellycamApplication, create_skellycam_app

from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pipeline.pipeline_manager import PipelineManager
from freemocap.core.tasks.frontend_payload_builder.frontend_paylod_builder import FrontendPayloadBuilder
from freemocap.core.types.type_overloads import PipelineIdString

logger = logging.getLogger(__name__)


@dataclass
class FreemocApp:
    global_kill_flag: multiprocessing.Value
    pipeline_shutdown_event: multiprocessing.Event
    skellycam_app: SkellycamApplication
    pipeline_manager: PipelineManager
    frontend_payload_builder: FrontendPayloadBuilder = field(default_factory=FrontendPayloadBuilder)

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value):
        skellycam_app = create_skellycam_app(global_kill_flag=global_kill_flag)
        pipeline_manager = PipelineManager(global_kill_flag=global_kill_flag)
        frontend_frame_builder = FrontendPayloadBuilder(
            camera_group_manager=skellycam_app.camera_group_manager,
            pipeline_manager=pipeline_manager
        )
        return cls(global_kill_flag=global_kill_flag,
                   pipeline_shutdown_event=multiprocessing.Event(),
                   skellycam_app=skellycam_app,
                   pipeline_manager=pipeline_manager,
                   frontend_payload_builder=frontend_frame_builder

                   )

    @property
    def should_continue(self) -> bool:
        return not self.global_kill_flag.value

    @property
    def camera_group_manager(self):
        return self.skellycam_app.camera_group_manager

    def connect_pipeline(self,
                         camera_group: CameraGroup,
                         pipeline_config: PipelineConfig) -> tuple[CameraGroupIdString, PipelineIdString]:
        pipeline = self.pipeline_manager.create_pipeline(camera_group=camera_group, pipeline_config=pipeline_config)
        return camera_group.id, pipeline.id

    def disconnect_pipeline(self):
        self.pipeline_manager.close_all_pipelines()

    def get_latest_frontend_payloads(self):
        return self.frontend_payload_builder.build_frontend_payloads(
            pipeline_manager=self.pipeline_manager,
            camera_group_manager=self.camera_group_manager
        )

    def close(self):
        self.global_kill_flag.value = True
        self.pipeline_shutdown_event.set()
        self.pipeline_manager.close_all_pipelines()
        self.skellycam_app.shutdown_skellycam() if self.skellycam_app else None


FREEMOCAP_APP: FreemocApp | None = None


def create_freemocap_app(global_kill_flag: multiprocessing.Value) -> FreemocApp:
    global FREEMOCAP_APP
    if FREEMOCAP_APP is None:
        FREEMOCAP_APP = FreemocApp.create(global_kill_flag=global_kill_flag)
    else:
        raise ValueError("FreemocApp already exists!")
    return FREEMOCAP_APP


def get_freemocap_app() -> FreemocApp:
    global FREEMOCAP_APP
    if FREEMOCAP_APP is None:
        raise ValueError("FreemocApp does not exist!")
    return FREEMOCAP_APP
