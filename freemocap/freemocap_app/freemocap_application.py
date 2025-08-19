import logging
import multiprocessing
from dataclasses import dataclass, field

from skellycam.core.types.type_overloads import CameraGroupIdString
from skellycam.skellycam_app.skellycam_app import SkellycamApplication, create_skellycam_app
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO
from freemocap.core.types.type_overloads import PipelineIdString
from freemocap.pipelines.dummy_pipeline import DummyPipeline
from freemocap.pipelines.pipeline_abcs import BaseProcessingPipeline
from freemocap.pipelines.pipeline_types import PipelineTypes

logger = logging.getLogger(__name__)



@dataclass
class PipelineManager:
    global_kill_flag: multiprocessing.Value
    pipelines: dict[PipelineIdString, PipelineTypes] = field(default_factory=dict)

    def create_pipeline(self, camera_group_shm_dto: CameraGroupSharedMemoryDTO ) -> BaseProcessingPipeline:
        return DummyPipeline.create(camera_group_shm_dto=camera_group_shm_dto,
                                    shutdown_event=self.global_kill_flag
                                    )


@dataclass
class FreemocapApplication:
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

    def create_pipeline(self, camera_group_id: CameraGroupIdString) -> tuple[CameraGroupIdString, PipelineIdString]:
        if len(self.skellycam_app.camera_group_manager.camera_groups) == 0:
            raise ValueError("No camera groups available to create a processing pipeline! Start a camera group first.")

        if camera_group_id is None:
            camera_group_id = list(self.skellycam_app.camera_group_manager.camera_groups.keys())[0]
        else:
            if camera_group_id not in self.skellycam_app.camera_group_manager.camera_groups:
                raise ValueError(f"Camera group ID {camera_group_id} does not exist!")

    def old_create_processing_pipeline(self, pipeline_type: PipelineTypes):
        from freemocap.pipelines.calibration_pipeline import CalibrationPipelineConfig, CalibrationPipeline
        from freemocap.pipelines.dummy_pipeline import DummyPipeline, DummyPipelineConfig
        from freemocap.pipelines.mocap_pipeline import MocapPipeline, MocapPipelineConfig
        from skellytracker.trackers.charuco_tracker import CharucoTrackerConfig
        from skellytracker.trackers.mediapipe_tracker import MediapipeTrackerConfig
        if not self.frame_escape_shm:
            raise ValueError("Cannot create image processing server without frame escape shared memory!")

        self.pipeline_shutdown_event.clear()

        if pipeline_type == PipelineTypes.CALIBRATION:
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
