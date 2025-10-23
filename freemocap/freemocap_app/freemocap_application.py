import logging
import multiprocessing
from dataclasses import dataclass, field

from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.types.type_overloads import CameraGroupIdString
from skellycam.skellycam_app.skellycam_app import SkellycamApplication, create_skellycam_app

from freemocap.core.types.type_overloads import PipelineIdString
from freemocap.core.pipeline.processing_pipeline import ProcessingPipeline
from freemocap.core.pipeline.pipeline_configs import PipelineConfig

logger = logging.getLogger(__name__)



@dataclass
class PipelineManager:
    global_kill_flag: multiprocessing.Value
    pipelines: dict[PipelineIdString, ProcessingPipeline] = field(default_factory=dict)

    def create_pipeline(self, camera_group:CameraGroup, pipeline_config:PipelineConfig ) -> ProcessingPipeline:
        pipeline =  ProcessingPipeline.from_camera_group(camera_group=camera_group,
                                                        pipeline_config=pipeline_config)
        pipeline.start()
        self.pipelines[pipeline.id] = pipeline
        logger.info(f"Created pipeline with ID: {pipeline.id} for camera group ID: {camera_group.id}")
        return pipeline

    def close_all_pipelines(self):
        for pipeline in self.pipelines.values():
            pipeline.shutdown()
        self.pipelines.clear()
        logger.info("All pipelines closed successfully")


@dataclass
class FreemocApp:
    global_kill_flag: multiprocessing.Value
    pipeline_shutdown_event: multiprocessing.Event
    skellycam_app: SkellycamApplication
    pipeline_manager: PipelineManager

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value):
        return cls(global_kill_flag=global_kill_flag,
                   pipeline_shutdown_event=multiprocessing.Event(),
                   skellycam_app=create_skellycam_app(global_kill_flag=global_kill_flag),
                   pipeline_manager=PipelineManager(global_kill_flag=global_kill_flag)
                   )

    @property
    def should_continue(self) -> bool:
        return not self.global_kill_flag.value

    def connect_pipeline(self, camera_group: CameraGroup, pipeline_config:PipelineConfig) -> tuple[CameraGroupIdString, PipelineIdString]:
        if len(self.skellycam_app.camera_group_manager.camera_groups) == 0:
            raise ValueError("No camera groups available to create a processing pipeline! Start a camera group first.")
        pipeline = self.pipeline_manager.create_pipeline(camera_group=camera_group, pipeline_config=pipeline_config)
        return camera_group.id, pipeline.id

    def disconnect_pipeline(self):
        self.pipeline_manager.close_all_pipelines()

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
