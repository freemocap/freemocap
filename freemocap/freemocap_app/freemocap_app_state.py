import logging
import multiprocessing
from dataclasses import dataclass
from typing import Optional

from skellycam.core.camera_group.shmorchestrator.shared_memory.multi_frame_escape_ring_buffer import \
    MultiFrameEscapeSharedMemoryRingBuffer
from skellycam.core.camera_group.shmorchestrator.shared_memory.single_slot_camera_group_shared_memory import \
    SingleSlotCameraGroupSharedMemory, CameraSharedMemoryDTOs
from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import create_skellycam_app_controller
from skellycam.skellycam_app.skellycam_app_state import SkellycamAppState, get_skellycam_app_state

from freemocap.pipelines.calibration_pipeline.calibration_pipeline_main import CalibrationPipelineConfig, \
    CalibrationProcessingServer
from freemocap.pipelines.pipeline_abcs import BaseProcessingServer

logger = logging.getLogger(__name__)


@dataclass
class FreemocapAppState:
    global_kill_flag: multiprocessing.Value
    pipeline_shutdown_event: multiprocessing.Event
    skellycam_app_state: SkellycamAppState
    camera_group_shm: SingleSlotCameraGroupSharedMemory | None = None

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

    def get_camera_shm_dtos(self) -> CameraSharedMemoryDTOs:
        if not self.camera_group_shm:
            self._create_camera_group_shm()
        return {camera_id: shm.to_dto() for camera_id, shm in self.camera_group_shm.camera_shms.items()}

    def _create_camera_group_shm(self):
        if self.skellycam_app_state.camera_group is None:
            raise ValueError("Cannot get RingBufferCameraSharedMemory without CameraGroup!")
        self.camera_group_shm = SingleSlotCameraGroupSharedMemory.create(camera_configs=self.camera_configs,
                                                                         read_only=True)

    def create_processing_server(self) -> BaseProcessingServer:
        if not self.frame_escape_shm:
            raise ValueError("Cannot create image processing server without frame escape shared memory!")

        self.pipeline_shutdown_event.clear()

        # if processing_server_type == ProcessingServerTypes.DUMMY:
        #     return processing_server_type.value.create(
        #         pipeline_config=DummyPipelineConfig.create(camera_configs=self.camera_configs),
        #         camera_shm_dtos=self.get_camera_shm_dtos(),
        #         shutdown_event=self.pipeline_shutdown_event,
        #     )

        return CalibrationProcessingServer.create(
            pipeline_config=CalibrationPipelineConfig.create(camera_configs=self.camera_configs),
            camera_shm_dtos=self.get_camera_shm_dtos(),
            shutdown_event=self.pipeline_shutdown_event,
        )

    def close(self):
        self.pipeline_shutdown_event.set()
        self.skellycam_app_state.close()

        if self.camera_group_shm:
            self.camera_group_shm.close_and_unlink()


FREEMOCAP_APP_STATE: FreemocapAppState|None = None


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
