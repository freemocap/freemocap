import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString
from skellycam.skellycam_app.skellycam_app import SkellycamApplication, create_skellycam_app

from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pipeline.pipeline_manager import PipelineManager
from freemocap.core.pipeline.processing_pipeline import FrontendPayload
from freemocap.core.pubsub.pubsub_topics import AggregationNodeOutputMessage
from freemocap.core.tasks.calibration_task.calibration_helpers.charuco_overlay_data import CharucoOverlayData
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt

logger = logging.getLogger(__name__)


@dataclass
class FreemocApp:
    global_kill_flag: multiprocessing.Value
    pipeline_shutdown_event: multiprocessing.Event
    skellycam_app: SkellycamApplication
    pipeline_manager: PipelineManager

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value):
        skellycam_app = create_skellycam_app(global_kill_flag=global_kill_flag)
        pipeline_manager = PipelineManager(global_kill_flag=global_kill_flag)
        return cls(global_kill_flag=global_kill_flag,
                   pipeline_shutdown_event=multiprocessing.Event(),
                   skellycam_app=skellycam_app,
                   pipeline_manager=pipeline_manager,
                   )

    @property
    def should_continue(self) -> bool:
        return not self.global_kill_flag.value

    @property
    def camera_group_manager(self):
        return self.skellycam_app.camera_group_manager

    def connect_pipeline(self,
                         pipeline_config: PipelineConfig) -> tuple[CameraGroupIdString, PipelineIdString]:
        pipeline = self.pipeline_manager.create_pipeline(pipeline_config=pipeline_config)
        return pipeline.camera_group_id, pipeline.id

    def disconnect_pipeline(self):
        self.pipeline_manager.close_all_pipelines()

    def get_latest_frontend_payloads(self, if_newer_than: FrameNumberInt) -> dict[PipelineIdString, tuple[bytes,FrontendPayload]]:
        if len(self.pipeline_manager.pipelines) == 0:
            return {}

        return self.pipeline_manager.get_latest_frontend_payloads(if_newer_than=if_newer_than)


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
