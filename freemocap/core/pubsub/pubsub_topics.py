from functools import cached_property
from typing import Type

import numpy as np
from pydantic import Field, model_validator

from skellycam.core.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.ipc.pubsub.pubsub_abcs import TopicMessageABC, PubSubTopicABC
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO
from skellycam.core.recorders.framerate_tracker import CurrentFramerate
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE
from skellycam.core.types.type_overloads import TopicPublicationQueue, CameraIdString
from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import LogRecordModel, \
    get_websocket_log_queue


class DeviceExtractedConfigMessage(TopicMessageABC):
    extracted_config: CameraConfig


class UpdateCamerasSettingsMessage(TopicMessageABC):
    requested_configs: CameraConfigs


class SetShmMessage(TopicMessageABC):
    camera_group_shm_dto: CameraGroupSharedMemoryDTO


class RecordingInfoMessage(TopicMessageABC):
    recording_info: RecordingInfo


class RecordingFinishedMessage(TopicMessageABC):
    recording_info: RecordingInfo
    frame_metadatas: list[np.recarray]


    @model_validator(mode='after')
    def validate_frame_metadatas(self):
        
        if not self.frame_metadatas:
            raise ValueError("RecordingFinishedMessage must have at least one frame_metadata.")
        
        # Check that all frame_metadatas are numpy recarrays with the correct dtype
        if not all(isinstance(md, np.recarray) for md in self.frame_metadatas):
            raise TypeError("All frame_metadatas must be instances of numpy.recarray.")
        
        if not all(md.dtype == FRAME_METADATA_DTYPE for md in self.frame_metadatas):
            raise TypeError(f"All frame_metadatas must have dtype {FRAME_METADATA_DTYPE}.")
        
        # Check that all frame_metadatas have the same camera_id
        first_camera_id = self.frame_metadatas[0].camera_config.camera_id[0]
        if not all(md.camera_config.camera_id[0] == first_camera_id for md in self.frame_metadatas):
            raise ValueError("All frame_metadatas must have the same camera_id.")
        
        # Check that frame numbers are sequential
        prev_frame_number = self.frame_metadatas[0].frame_number[0] - 1
        for md in self.frame_metadatas:
            if md.frame_number[0] != prev_frame_number + 1:
                raise ValueError("Frame numbers in frame_metadatas must be sequential.")
            prev_frame_number = md.frame_number[0]
        
        return self

    @cached_property
    def camera_id(self) -> CameraIdString:
        return self.frame_metadatas[0].camera_config.camera_id[0]  # validated on model creation

class FramerateMessage(TopicMessageABC):
    current_framerate: CurrentFramerate


class UpdateCamerasSettingsTopic(PubSubTopicABC):
    message_type: Type[UpdateCamerasSettingsMessage] = UpdateCamerasSettingsMessage


class DeviceExtractedConfigTopic(PubSubTopicABC):
    message_type: Type[DeviceExtractedConfigMessage] = DeviceExtractedConfigMessage


class SetShmTopic(PubSubTopicABC):
    message_type: Type[SetShmMessage] = SetShmMessage


class RecordingInfoTopic(PubSubTopicABC):
    message_type: Type[RecordingInfoMessage] = RecordingInfoMessage


class RecordingFinishedTopic(PubSubTopicABC):
    message_type: Type[RecordingFinishedMessage] = RecordingFinishedMessage


class FramerateTopic(PubSubTopicABC):
    message_type: Type[FramerateMessage] = FramerateMessage


class LogsTopic(PubSubTopicABC):
    message_type: Type[LogRecordModel] = LogRecordModel
    publication: TopicPublicationQueue = Field(default_factory=get_websocket_log_queue)
