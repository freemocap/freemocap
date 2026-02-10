"""
RealtimeCameraNode: reads frames from shared memory, runs enabled detectors,
publishes CameraNodeOutputMessages.

Runs indefinitely until shutdown. Responds to pipeline config updates
(toggling detectors, changing charuco board params, etc).
"""
import logging
import multiprocessing
import time
from dataclasses import dataclass

import cv2
import numpy as np
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
from skellycam.core.types.type_overloads import CameraIdString, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms
from skellytracker.trackers.charuco_tracker.charuco_detector import CharucoDetector
from skellytracker.trackers.mediapipe_tracker.mediapipe_detector import MediapipeDetector

from freemocap.core.pipeline.pipeline_configs import RealtimePipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.nodes import BaseNode
from freemocap.pubsub.pubsub_topics import (
    ProcessFrameNumberTopic,
    PipelineConfigUpdateTopic,
    CameraNodeOutputTopic,
    PipelineConfigUpdateMessage,
    ProcessFrameNumberMessage,
    CameraNodeOutputMessage,
)
from skellycam.core.ipc.process_management.process_registry import ProcessRegistry

logger = logging.getLogger(__name__)


@dataclass
class RealtimeCameraNode(BaseNode):
    camera_id: CameraIdString

    @classmethod
    def create(
        cls,
        *,
        camera_id: CameraIdString,
        camera_shm_dto: SharedMemoryRingBufferDTO,
        process_registry: ProcessRegistry,
        config: RealtimePipelineConfig,
        ipc: PipelineIPC,
    ) -> "RealtimeCameraNode":
        shutdown_self_flag = multiprocessing.Value('b', False)
        worker = process_registry.create_process(
            target=cls._run,
            name=f"RealtimeCameraNode-{camera_id}",
            kwargs=dict(
                camera_id=camera_id,
                ipc=ipc,
                config=config,
                shutdown_self_flag=shutdown_self_flag,
                camera_shm_dto=camera_shm_dto,
                process_frame_number_subscription=ipc.pubsub.get_subscription(
                    ProcessFrameNumberTopic,
                ),
                pipeline_config_subscription=ipc.pubsub.get_subscription(
                    PipelineConfigUpdateTopic,
                ),
            ),
            log_queue=ipc.ws_queue,
        )
        return cls(
            camera_id=camera_id,
            shutdown_self_flag=shutdown_self_flag,
            worker=worker,
        )

    @staticmethod
    def _run(
        *,
        camera_id: CameraIdString,
        ipc: PipelineIPC,
        config: RealtimePipelineConfig,
        process_frame_number_subscription: TopicSubscriptionQueue,
        pipeline_config_subscription: TopicSubscriptionQueue,
        shutdown_self_flag: multiprocessing.Value,
        camera_shm_dto: SharedMemoryRingBufferDTO,
    ) -> None:
        logger.debug(f"RealtimeCameraNode [{camera_id}] initializing")
        camera_shm = CameraSharedMemoryRingBuffer.recreate(
            dto=camera_shm_dto,
            read_only=False,
        )

        # Create detectors based on initial config
        charuco_detector: CharucoDetector | None = None
        mediapipe_detector: MediapipeDetector | None = None

        if config.calibration_detection_enabled:
            charuco_detector = CharucoDetector.create(
                config=config.calibration_config.detector_config,
            )
        if config.mocap_detection_enabled:
            mediapipe_detector = MediapipeDetector.create(
                config=config.mocap_config.detector_config,
            )

        frame_rec_array: np.recarray | None = None

        try:
            logger.debug(f"RealtimeCameraNode [{camera_id}] entering main loop")
            while ipc.should_continue and not shutdown_self_flag.value:
                wait_1ms()

                # ---- Handle config updates ----
                while not pipeline_config_subscription.empty():
                    update_msg: PipelineConfigUpdateMessage = pipeline_config_subscription.get()
                    new_config = update_msg.pipeline_config
                    logger.debug(f"RealtimeCameraNode [{camera_id}] received config update")

                    # Recreate detectors if toggled or config changed
                    if new_config.calibration_detection_enabled and charuco_detector is None:
                        charuco_detector = CharucoDetector.create(
                            config=new_config.calibration_config.detector_config,
                        )
                    elif not new_config.calibration_detection_enabled:
                        charuco_detector = None

                    if new_config.mocap_detection_enabled and mediapipe_detector is None:
                        mediapipe_detector = MediapipeDetector.create(
                            config=new_config.mocap_config.detector_config,
                        )
                    elif not new_config.mocap_detection_enabled:
                        mediapipe_detector = None

                    config = new_config

                # ---- Process frames ----
                if process_frame_number_subscription.empty():
                    continue

                frame_msg: ProcessFrameNumberMessage = process_frame_number_subscription.get()
                frame_rec_array = camera_shm.get_data_by_index(
                    index=frame_msg.frame_number,
                    rec_array=frame_rec_array,
                )

                # Handle image rotation
                if frame_rec_array.frame_metadata.camera_config.rotation != -1:
                    image = cv2.rotate(
                        src=frame_rec_array.image[0],
                        rotateCode=frame_rec_array.frame_metadata.camera_config.rotation[0],
                    )
                else:
                    image = frame_rec_array.image[0]

                actual_frame_number: int = frame_rec_array.frame_metadata.frame_number[0]
                actual_camera_id: CameraIdString = frame_rec_array.frame_metadata.camera_config.camera_id[0]

                # Run the active detector and publish
                # Priority: mediapipe for mocap, charuco for calibration
                # TODO: support running both and publishing separate messages
                if mediapipe_detector is not None:
                    observation = mediapipe_detector.detect(
                        frame_number=actual_frame_number,
                        image=image,
                    )
                elif charuco_detector is not None:
                    observation = charuco_detector.detect(
                        frame_number=actual_frame_number,
                        image=image,
                    )
                else:
                    # No detectors enabled, skip
                    continue

                ipc.pubsub.publish(
                    topic_type=CameraNodeOutputTopic,
                    message=CameraNodeOutputMessage(
                        camera_id=actual_camera_id,
                        frame_number=actual_frame_number,
                        observation=observation,
                    ),
                )

        except Exception as e:
            logger.exception(f"Exception in RealtimeCameraNode [{camera_id}]: {e}")
            ipc.kill_everything()
            raise
        finally:
            logger.debug(f"RealtimeCameraNode [{camera_id}] exiting")
