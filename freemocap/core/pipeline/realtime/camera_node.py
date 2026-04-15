"""
RealtimeCameraNode: reads frames from shared memory, runs enabled detectors,
publishes CameraNodeOutputMessages.

Runs indefinitely until shutdown. Responds to pipeline config updates
(toggling detectors, changing charuco board params, etc).
"""
import logging
import multiprocessing
from dataclasses import dataclass
from multiprocessing.sharedctypes import Synchronized
from typing import TYPE_CHECKING

from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
from skellycam.core.types.type_overloads import CameraIdString, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms
from skellytracker.trackers.legacy_mediapipe_tracker.legacy_mediapipe_detector import LegacyMediapipeDetector

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.abcs.source_node_abc import SourceNode
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.types.type_overloads import TopicPublicationQueue
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import (
    ProcessFrameNumberTopic,
    PipelineConfigUpdateTopic,
    CameraNodeOutputTopic,
    PipelineConfigUpdateMessage,
    ProcessFrameNumberMessage,
    CameraNodeOutputMessage,
)

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CameraNode(SourceNode):
    camera_id:CameraIdString

    @classmethod
    def create(
        cls,
        *,
        camera_id: CameraIdString,
        camera_shm_dto: SharedMemoryRingBufferDTO,
        worker_registry: WorkerRegistry,
        config: CameraNodeConfig,
        ipc: PipelineIPC,
        pubsub: PubSubTopicManager,
    ) -> "CameraNode":
        shutdown_self_flag, worker = cls._create_worker(
            target=cls._run,
            name=f"RealtimeCameraNode-{camera_id}",
            worker_registry=worker_registry,
            log_queue=ipc.ws_queue,
            kwargs=dict(
                camera_id=camera_id,
                ipc=ipc,
                config=config,
                camera_shm_dto=camera_shm_dto,
                process_frame_number_sub=pubsub.get_subscription(
                    ProcessFrameNumberTopic,
                ),
                pipeline_config_sub=pubsub.get_subscription(
                    PipelineConfigUpdateTopic,
                ),
                camera_output_pub=pubsub.get_publication_queue(
                    CameraNodeOutputTopic,
                ),
            ),
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
        config: CameraNodeConfig,
        process_frame_number_sub: TopicSubscriptionQueue,
        pipeline_config_sub: TopicSubscriptionQueue,
        camera_output_pub: TopicPublicationQueue,
        shutdown_self_flag: Synchronized,
        camera_shm_dto: SharedMemoryRingBufferDTO,
    ) -> None:
        import cv2
        from skellytracker.trackers.charuco_tracker.charuco_detector import CharucoDetector

        logger.debug(f"RealtimeCameraNode [{camera_id}] initializing")
        camera_shm = CameraSharedMemoryRingBuffer.recreate(
            dto=camera_shm_dto,
            read_only=False,
        )

        charuco_detector: CharucoDetector | None = None
        mediapipe_detector: LegacyMediapipeDetector | None = None

        if config.charuco_tracking_enabled and config.charuco_detector_config is not None:
            charuco_detector = CharucoDetector.create(
                config=config.charuco_detector_config,
            )
        if config.skeleton_tracking_enabled and config.skeleton_detector_config is not None:
            mediapipe_detector = LegacyMediapipeDetector.create(
                config=config.skeleton_detector_config ,
            )

        frame_rec_array: np.recarray | None = None

        try:
            logger.debug(f"RealtimeCameraNode [{camera_id}] entering main loop")
            while ipc.should_continue and not shutdown_self_flag.value:
                wait_1ms()

                # ---- Handle config updates ----
                while not pipeline_config_sub.empty():
                    update_msg: PipelineConfigUpdateMessage = pipeline_config_sub.get()
                    new_config:CameraNodeConfig = update_msg.pipeline_config.camera_node_config
                    logger.debug(f"RealtimeCameraNode [{camera_id}] received config update")

                    if new_config.charuco_tracking_enabled and new_config.charuco_detector_config is not None:
                        charuco_detector = CharucoDetector.create(
                            config=new_config.charuco_detector_config,
                        )
                    elif not new_config.charuco_tracking_enabled:
                        charuco_detector = None

                    if new_config.skeleton_tracking_enabled and new_config.skeleton_detector_config is not None:
                        mediapipe_detector = LegacyMediapipeDetector.create(
                            config=new_config.skeleton_detector_config,
                        )
                    elif not new_config.skeleton_tracking_enabled:
                        mediapipe_detector = None

                    config = new_config

                # ---- Check shared memory validity every iteration ----
                if not camera_shm.valid:
                    logger.debug(
                        f"RealtimeCameraNode [{camera_id}] "
                        f"shared memory invalidated, exiting"
                    )
                    break

                # ---- Process frames ----
                if process_frame_number_sub.empty():
                    continue

                frame_msg: ProcessFrameNumberMessage = process_frame_number_sub.get()
                frame_rec_array = camera_shm.get_data_by_index(
                    index=frame_msg.frame_number,
                    rec_array=frame_rec_array,
                )

                if frame_rec_array.frame_metadata.camera_config.rotation != -1:
                    image = cv2.rotate(
                        src=frame_rec_array.image[0],
                        rotateCode=frame_rec_array.frame_metadata.camera_config.rotation[0],
                    )
                else:
                    image = frame_rec_array.image[0]

                actual_frame_number: int = frame_rec_array.frame_metadata.frame_number[0]
                actual_camera_id: CameraIdString = frame_rec_array.frame_metadata.camera_config.camera_id[0]

                if actual_frame_number != frame_msg.frame_number:
                    logger.warning(
                        f"RealtimeCameraNode [{camera_id}]: requested frame {frame_msg.frame_number} "
                        f"but ring buffer contained frame {actual_frame_number} — possible ring buffer overwrite"
                    )
                mediapipe_observation = None
                charuco_observation = None
                if mediapipe_detector is not None:
                    mediapipe_observation = mediapipe_detector.detect(
                        frame_number=actual_frame_number,
                        image=image,
                    )
                if charuco_detector is not None:
                    charuco_observation = charuco_detector.detect(
                        frame_number=actual_frame_number,
                        image=image,
                    )

                camera_output_pub.put(
                    CameraNodeOutputMessage(
                        camera_id=actual_camera_id,
                        frame_number=actual_frame_number,
                        charuco_observation=charuco_observation,
                        mediapipe_observation = mediapipe_observation
                    ),
                )

        except Exception as e:
            logger.exception(f"Exception in RealtimeCameraNode [{camera_id}]: {e}")
            ipc.kill_everything()
            raise
        finally:
            logger.debug(f"RealtimeCameraNode [{camera_id}] exiting")
