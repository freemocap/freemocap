import logging
import multiprocessing
from dataclasses import dataclass
from typing import Optional

from skellycam.core.camera_group.shmorchestrator.shared_memory.multi_frame_escape_ring_buffer import \
    MultiFrameEscapeSharedMemoryRingBuffer
from skellycam.skellycam_app.skellycam_app_state import SkellycamAppState, get_skellycam_app_state
from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import create_skellycam_app_controller

from freemocap.pipelines.pipeline_abcs import FreemocapProcessingServer

logger = logging.getLogger(__name__)


@dataclass
class FreemocapAppState:
    global_kill_flag: multiprocessing.Value
    skellycam_app_state: SkellycamAppState
    processing_server: ProcessingServer|None = None
    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value):
        create_skellycam_app_controller(global_kill_flag=global_kill_flag)

        return cls(global_kill_flag=global_kill_flag,
                   skellycam_app_state=get_skellycam_app_state())

    @property
    def frame_escape_shm(self) -> MultiFrameEscapeSharedMemoryRingBuffer:
        return self.skellycam_app_state.shmorchestrator.multi_frame_escape_ring_shm

    @property
    def skellycam_ipc_flags(self):
        return self.skellycam_app_state.ipc_flags

    @property
    def skellycam_ipc_queue(self):
        return self.skellycam_app_state.ipc_queue

    def create_image_processing_server(self, processing_server: FreemocapProcessingServer):
        if not self.frame_escape_shm:
            raise ValueError("Cannot create image processing server without frame escape shared memory!")
        return FreemocapProcessingServer.create(skellycam_app_state=self.skellycam_app_state)



FREEMOCAP_APP_STATE: Optional[FreemocapAppState] = None
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