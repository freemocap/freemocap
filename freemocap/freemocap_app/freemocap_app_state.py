import logging
import multiprocessing
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel


logger = logging.getLogger(__name__)


@dataclass
class FreemocapAppState:

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value):
        return cls(ipc_flags=IPCFlags(global_kill_flag=global_kill_flag),
                   ipc_queue=multiprocessing.Queue(),
                   config_update_queue=multiprocessing.Queue())


    @property
    def frame_escape_shm(self) -> MultiFrameEscapeSharedMemoryRingBuffer:
        return self.shmorchestrator.multi_frame_escape_ring_shm

    @property
    def camera_group_configs(self) -> Optional[CameraConfigs]:
        if self.camera_group is None:
            if self.available_devices is None:
                raise ValueError("Cannot get CameraConfigs without available devices!")
            return available_devices_to_default_camera_configs(self.available_devices)
        return self.camera_group.camera_configs

    def set_available_devices(self, value: AvailableDevices):
        self.available_devices = value
        self.ipc_queue.put(self.state_dto())

    def create_camera_group(self, camera_configs: CameraConfigs):
        if camera_configs is None:
            raise ValueError("Cannot create CameraGroup without camera_configs!")
        # if self.available_devices is None:
        #     raise ValueError("Cannot get CameraConfigs without available devices!")
        self.camera_group_dto = CameraGroupDTO(camera_configs=camera_configs,
                                               ipc_queue=self.ipc_queue,
                                               ipc_flags=self.ipc_flags,
                                               config_update_queue=self.config_update_queue,
                                               group_uuid=str(uuid4())
                                               )
        self.shmorchestrator = CameraGroupSharedMemoryOrchestrator.create(camera_group_dto=self.camera_group_dto,
                                                                          ipc_flags=self.ipc_flags,
                                                                          read_only=True)
        self.camera_group = CameraGroup.create(camera_group_dto=self.camera_group_dto,
                                               shmorc_dto=self.shmorchestrator.to_dto()
                                               )

        logger.info(f"Camera group created successfully for cameras: {self.camera_group.camera_ids}")

    def update_camera_group(self,
                            camera_configs: CameraConfigs,
                            update_instructions: UpdateInstructions):
        if self.camera_group is None:
            raise ValueError("Cannot update CameraGroup if it does not exist!")
        self.camera_group.update_camera_configs(camera_configs=camera_configs,
                                                update_instructions=update_instructions)

    def close_camera_group(self):
        if self.camera_group is None:
            logger.warning("Camera group does not exist, so it cannot be closed!")
            return
        logger.debug("Closing existing camera group...")
        self.camera_group.close()
        self.shmorchestrator.close_and_unlink()
        self._reset()
        logger.success("Camera group closed successfully")

    def start_recording(self):
        self.ipc_flags.record_frames_flag.value = True
        self.ipc_queue.put(self.state_dto())

    def stop_recording(self):
        self.ipc_flags.record_frames_flag.value = False
        self.ipc_queue.put(self.state_dto())

    def state_dto(self):
        return AppStateDTO.from_state(self)

    def _reset(self):
        self.camera_group = None
        self.shmorchestrator = None
        self.current_framerate = None
        self.ipc_flags = IPCFlags(global_kill_flag=self.ipc_flags.global_kill_flag)


class AppStateDTO(BaseModel):
    """
    Serializable Data Transfer Object for the AppState
    """
    type: str = "AppStateDTO"
    state_timestamp: str = datetime.now().isoformat()

    camera_configs: Optional[CameraConfigs]
    available_devices: Optional[AvailableDevices]
    current_framerate: Optional[CurrentFrameRate]
    record_frames_flag_status: bool

    @classmethod
    def from_state(cls, state: FreemocapAppState):
        return cls(
            camera_configs=state.camera_group_configs,
            available_devices=state.available_devices,
            current_framerate=state.current_framerate,
            record_frames_flag_status=state.ipc_flags.record_frames_flag.value,
        )
