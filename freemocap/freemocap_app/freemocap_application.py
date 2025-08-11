import logging
import multiprocessing
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel

from skellycam.skellycam_app.skellycam_app import SkellycamApplication, get_skellycam_app, create_skellycam_app




from freemocap.pipelines.pipeline_types import PipelineTypes

logger = logging.getLogger(__name__)


@dataclass
class FreemocapApplication:
    global_kill_flag: multiprocessing.Value
    pipeline_shutdown_event: multiprocessing.Event
    skellycam_app: SkellycamApplication

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value):

        return cls(global_kill_flag=global_kill_flag,
                   pipeline_shutdown_event=multiprocessing.Event(),
                   skellycam_app=create_skellycam_app(global_kill_flag=global_kill_flag))


    def create_processing_pipeline(self, pipeline_type: PipelineTypes):
        from freemocap.pipelines.calibration_pipeline import CalibrationPipelineConfig, CalibrationPipeline
        from freemocap.pipelines.dummy_pipeline import DummyPipeline, DummyPipelineConfig
        from freemocap.pipelines.mocap_pipeline import MocapPipeline, MocapPipelineConfig
        from skellytracker.trackers.charuco_tracker import CharucoTrackerConfig
        from skellytracker.trackers.mediapipe_tracker import MediapipeTrackerConfig
        if not self.frame_escape_shm:
            raise ValueError("Cannot create image processing server without frame escape shared memory!")

        self.pipeline_shutdown_event.clear()

        if pipeline_type  == PipelineTypes.CALIBRATION:
            return CalibrationPipeline.create(
                config=CalibrationPipelineConfig.create(camera_configs=self.camera_configs,
                                                                 tracker_config=CharucoTrackerConfig()
                                                                 ),
                camera_shm_dtos=self.get_processor_camera_shms_dtos(),
                shutdown_event=self.pipeline_shutdown_event,
            )
        elif pipeline_type == PipelineTypes.MOCAP:
            return MocapPipeline.create(
                config=MocapPipelineConfig.create(camera_configs=self.camera_configs,
                                                    tracker_config=MediapipeTrackerConfig()
                                                  ),
                camera_shm_dtos=self.get_processor_camera_shms_dtos(),
                shutdown_event=self.pipeline_shutdown_event,
            )
        elif pipeline_type == PipelineTypes.DUMMY:
            return DummyPipeline.create(
                config=DummyPipelineConfig.create(camera_configs=self.camera_configs),
                camera_shm_dtos=self.get_processor_camera_shms_dtos(),
                shutdown_event=self.pipeline_shutdown_event,
            )
        else:
            raise ValueError(f"Unknown pipeline type: {pipeline_type}")

    def close(self):
        self.global_kill_flag.value = True
        self.pipeline_shutdown_event.set()
        self.skellycam_app.shutdown_skellycam() if self.skellycam_app else None






FREEMOCAP_APP: FreemocapApplication | None = None


def create_freemocap_app(global_kill_flag: multiprocessing.Value) -> FreemocapApplication:
    global FREEMOCAP_APP
    if FREEMOCAP_APP is None:
        FREEMOCAP_APP = FreemocapApplication.create(global_kill_flag=global_kill_flag)
    else:
        raise ValueError("FreemocapApplication already exists!")
    return FREEMOCAP_APP


def get_freemocap_app() -> FreemocapApplication:
    global FREEMOCAP_APP
    if FREEMOCAP_APP is None:
        raise ValueError("FreemocapApplication does not exist!")
    return FREEMOCAP_APP
