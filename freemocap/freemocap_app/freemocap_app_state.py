import logging
import multiprocessing
from dataclasses import dataclass
from typing import Optional

from skellycam.core.camera_group.shmorchestrator.shared_memory.multi_frame_escape_ring_buffer import \
    MultiFrameEscapeSharedMemoryRingBuffer
from skellycam.skellycam_app.skellycam_app_state import SkellycamAppState

logger = logging.getLogger(__name__)


@dataclass
class FreemocapAppState:
    global_kill_flag: multiprocessing.Value
    skellycam_app_state: Optional[SkellycamAppState] = None

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value):
        return cls(global_kill_flag=global_kill_flag,
                   skellycam_app_state=SkellycamAppState.create(global_kill_flag=global_kill_flag))

    @property
    def frame_escape_shm(self) -> MultiFrameEscapeSharedMemoryRingBuffer:
        return self.skellycam_app_state.shmorchestrator.multi_frame_escape_ring_shm
