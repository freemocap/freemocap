import logging
import multiprocessing
from pathlib import Path
from typing import Any
from typing import ClassVar

import cv2
import numpy as np
from pydantic import Field
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
from skellycam.core.types.type_overloads import CameraIdString
from skellycam.utilities.wait_functions import wait_1ms
from skellytracker.trackers.charuco_tracker.charuco_detector import CharucoDetector

from freemocap.core.pipeline.base_node_abcs import ProcessNodeABC
from freemocap.core.pipeline.base_node_abcs import ProcessNodeParams
from freemocap.core.pipeline.og.pipeline_configs import CalibrationTaskConfig, MocapTaskConfig
from freemocap.core.pipeline.og.pipeline_configs import PipelineConfig
from freemocap.core.pipeline.og.pipeline_ipc import PipelineIPC
from freemocap.core.types.type_overloads import TopicSubscriptionQueue
from freemocap.pubsub.pubsub_abcs import PubSubTopicABC
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import (
    CameraNodeOutputMessage,
    PipelineConfigUpdateMessage,
    ProcessFrameNumberMessage,
)
from freemocap.pubsub.pubsub_topics import (
    ProcessFrameNumberTopic,
    PipelineConfigUpdateTopic,
    CameraNodeOutputTopic,
)

logger = logging.getLogger(__name__)

class VideoNodeParams(ProcessNodeParams):
    """Parameters for video processing nodes (posthoc)."""

    # Declare subscription requirements
    subscribed_topics: ClassVar[list[type[PubSubTopicABC]]] = [
        ProcessFrameNumberTopic,
        PipelineConfigUpdateTopic,
    ]
    published_topics: ClassVar[list[type[PubSubTopicABC]]] = [
        CameraNodeOutputTopic,  # Same output as camera nodes
    ]

    video_path: Path
    camera_id: CameraIdString  # Still need camera ID for aggregation
    start_frame: int = Field(default=0, ge=0)
    end_frame: int | None = Field(default=None, ge=0)
    calibration_task_config: CalibrationTaskConfig = Field(default_factory=CalibrationTaskConfig)
    mocap_task_config: MocapTaskConfig = Field(default_factory=MocapTaskConfig)


class VideoNode(ProcessNodeABC):

    @classmethod
    def create(
            cls,
            *,
            node_id: str,
            params: VideoNodeParams,
            subscriptions: dict[type[PubSubTopicABC], TopicSubscriptionQueue],
            pubsub: PubSubTopicManager,
            subprocess_registry: list[multiprocessing.Process],
            camera_shm_dto: SharedMemoryRingBufferDTO,
            pipeline_config: PipelineConfig,
            ipc: PipelineIPC,
            **kwargs: Any
    ) -> "CameraNode":
        shutdown_flag = multiprocessing.Value('b', False)

        # Verify we have the required subscriptions
        required_topics = params.get_subscription_requirements()
        for topic in required_topics:
            if topic not in subscriptions:
                raise ValueError(f"Missing required subscription for {topic.__name__}")

        # Create worker process with all pre-allocated resources
        worker = multiprocessing.Process(
            target=cls._run,
            name=f"CameraNode-{params.camera_id}",
            kwargs=dict(
                node_id=node_id,
                params=params,
                subscriptions=subscriptions,
                pubsub=pubsub,
                shutdown_flag=shutdown_flag,
                camera_shm_dto=camera_shm_dto,
                pipeline_config=pipeline_config,
                ipc=ipc,
            ),
            daemon=True,
        )

        subprocess_registry.append(worker)

        return cls(
            node_id=node_id,
            params=params,
            subscriptions=subscriptions,
            pubsub=pubsub,
            shutdown_flag=shutdown_flag,
            worker=worker,
        )

    @staticmethod
    def _run(
            *,
            node_id: str,
            params: VideoNodeParams,
            subscriptions: dict[type[PubSubTopicABC], TopicSubscriptionQueue],
            pubsub: PubSubTopicManager,
            shutdown_flag: multiprocessing.Value,
            camera_shm_dto: SharedMemoryRingBufferDTO,
            pipeline_config: PipelineConfig,
            ipc: PipelineIPC,
            **kwargs: Any
    ) -> None:
        """
        Main process loop for camera node.
        Runs in child process with pre-allocated subscriptions.
        """
        # Configure logging for child process
        if multiprocessing.parent_process():
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.ws_queue)

        logger.debug(f"Starting camera node {node_id} for camera {params.camera_id}")

        # Get pre-allocated subscriptions
        process_frame_sub = subscriptions[ProcessFrameNumberTopic]
        config_update_sub = subscriptions[PipelineConfigUpdateTopic]

        # Initialize shared memory
        camera_shm = CameraSharedMemoryRingBuffer.recreate(
            dto=camera_shm_dto,
            read_only=False
        )

        # Initialize detector
        detector = CharucoDetector.create(
            config=params.calibration_task_config.detector_config
        )

        # Working variables
        current_config = pipeline_config
        frame_rec_array: np.recarray | None = None

        try:
            while ipc.should_continue and not shutdown_flag.value:
                wait_1ms()

                # Check for config updates
                while not config_update_sub.empty():
                    msg: PipelineConfigUpdateMessage = config_update_sub.get()
                    current_config = msg.pipeline_config
                    logger.info(f"Camera {params.camera_id} received config update")

                # Check for frame to process
                if not process_frame_sub.empty():
                    frame_msg: ProcessFrameNumberMessage = process_frame_sub.get()

                    # Process the frame
                    frame_rec_array = camera_shm.get_data_by_index(
                        index=frame_msg.frame_number,
                        rec_array=frame_rec_array
                    )

                    # Handle rotation if needed
                    image = frame_rec_array.image[0]
                    rotation = frame_rec_array.frame_metadata.camera_config.rotation[0]
                    if rotation != -1:
                        image = cv2.rotate(src=image, rotateCode=rotation)

                    # Detect charuco if enabled
                    charuco_observation = None
                    if current_config.calibration_task_config.live_track_charuco:
                        charuco_observation = detector.detect(
                            frame_number=frame_rec_array.frame_metadata.frame_number[0],
                            image=image,
                        )

                    # Publish result
                    output_msg = CameraNodeOutputMessage(
                        camera_id=params.camera_id,
                        frame_number=frame_rec_array.frame_metadata.frame_number[0],
                        charuco_observation=charuco_observation,
                    )

                    pubsub.publish(
                        topic_type=CameraNodeOutputTopic,
                        message=output_msg,
                    )

                    logger.trace(f"Camera {params.camera_id} processed frame {frame_msg.frame_number}")

        except Exception as e:
            logger.error(f"Error in camera node {node_id}: {e}", exc_info=True)
            ipc.kill_everything()
            raise

        finally:
            logger.debug(f"Shutting down camera node {node_id}")