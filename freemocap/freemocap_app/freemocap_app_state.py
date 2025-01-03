import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera_group.shmorchestrator.shared_memory.multi_frame_escape_ring_buffer import \
    MultiFrameEscapeSharedMemoryRingBuffer
from skellycam.core.camera_group.shmorchestrator.shared_memory.single_slot_camera_group_shared_memory import \
    SingleSlotCameraGroupSharedMemory, CameraSharedMemoryDTOs
from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import create_skellycam_app_controller
from skellycam.skellycam_app.skellycam_app_state import SkellycamAppState, get_skellycam_app_state
from skellytracker.trackers.charuco_tracker import CharucoTrackerConfig

from freemocap.pipelines.calibration_pipeline import CalibrationPipelineConfig, CalibrationPipeline

logger = logging.getLogger(__name__)


@dataclass
class FreemocapAppState:
    global_kill_flag: multiprocessing.Value
    pipeline_shutdown_event: multiprocessing.Event
    skellycam_app_state: SkellycamAppState
    processing_camera_shms: SingleSlotCameraGroupSharedMemory | None = None

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value):
        create_skellycam_app_controller(global_kill_flag=global_kill_flag)

        return cls(global_kill_flag=global_kill_flag,
                   pipeline_shutdown_event=multiprocessing.Event(),
                   skellycam_app_state=get_skellycam_app_state())

    @property
    def camera_configs(self):
        return self.skellycam_app_state.camera_group_configs

    @property
    def frame_escape_shm(self) -> MultiFrameEscapeSharedMemoryRingBuffer:
        return self.skellycam_app_state.shmorchestrator.multi_frame_escape_ring_shm

    @property
    def skellycam_ipc_flags(self):
        return self.skellycam_app_state.ipc_flags

    @property
    def skellycam_ipc_queue(self):
        return self.skellycam_app_state.ipc_queue


    def get_processor_camera_shms_dtos(self) -> CameraSharedMemoryDTOs:

        self._create_processing_camera_shms()
        return self.processing_camera_shms.camera_shm_dtos

    def _create_processing_camera_shms(self):
        if self.skellycam_app_state.camera_group is None:
            raise ValueError("Cannot create camera shared memory before camera group is initialized!")
        self.processing_camera_shms = SingleSlotCameraGroupSharedMemory.create(camera_configs=self.camera_configs,
                                                                         read_only=True)

    def create_processing_pipeline(self) -> CalibrationPipeline:
        if not self.frame_escape_shm:
            raise ValueError("Cannot create image processing server without frame escape shared memory!")

        self.pipeline_shutdown_event.clear()


        return CalibrationPipeline.create(
            config=CalibrationPipelineConfig.create(camera_configs=self.camera_configs,
                                                             tracker_config=CharucoTrackerConfig()
                                                             ),
            camera_shm_dtos=self.get_processor_camera_shms_dtos(),
            shutdown_event=self.pipeline_shutdown_event,
        )

    def close(self):
        self.global_kill_flag.value = True
        self.pipeline_shutdown_event.set()
        self.skellycam_app_state.close()

        if self.processing_camera_shms:
            self.processing_camera_shms.close_and_unlink()


FREEMOCAP_APP_STATE: FreemocapAppState | None = None


def create_freemocap_app_state(global_kill_flag: multiprocessing.Value) -> FreemocapAppState:
    global FREEMOCAP_APP_STATE
    if FREEMOCAP_APP_STATE is None:
        FREEMOCAP_APP_STATE = FreemocapAppState.create(global_kill_flag=global_kill_flag)
    else:
        raise ValueError("FreemocapAppState already exists!")
    return FREEMOCAP_APP_STATE


def get_freemocap_app_state() -> FreemocapAppState:
    global FREEMOCAP_APP_STATE
    if FREEMOCAP_APP_STATE is None:
        raise ValueError("FreemocapAppState does not exist!")
    return FREEMOCAP_APP_STATE
