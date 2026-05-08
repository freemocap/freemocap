"""
RealtimeCameraNode: reads frames from shared memory, runs enabled detectors,
publishes CameraNodeOutputMessages.

Runs indefinitely until shutdown. Responds to pipeline config updates
(toggling detectors, changing charuco board params, etc).
"""
import logging
import queue
import time
from dataclasses import dataclass
from multiprocessing.sharedctypes import Synchronized

from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
from skellycam.core.types.type_overloads import CameraIdString, TopicSubscriptionQueue
# from skellytracker.trackers.legacy_mediapipe_tracker.legacy_mediapipe_detector import LegacyMediapipeDetector

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.abcs.source_node_abc import SourceNode
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.types.type_overloads import TopicPublicationQueue
from freemocap.core.pipeline.pipeline_stage_timer import PipelineStageTimer
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import (
    ProcessFrameNumberTopic,
    PipelineConfigUpdateTopic,
    CameraNodeOutputTopic,
    PipelineConfigUpdateMessage,
    ProcessFrameNumberMessage,
    CameraNodeOutputMessage,
    PipelineTimingTopic,
)

import numpy as np
from skellytracker.trackers.rtmpose_tracker.rtmpose_detector import RTMPoseDetector

logger = logging.getLogger(__name__)


@dataclass
class CameraNode(SourceNode):
    camera_id: CameraIdString

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
            skeleton_inference_centralized: bool = False,
            log_pipeline_times: bool = False,
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
                skeleton_inference_centralized=skeleton_inference_centralized,
                log_pipeline_times=log_pipeline_times,
                process_frame_number_sub=pubsub.get_subscription(
                    ProcessFrameNumberTopic,
                ),
                pipeline_config_sub=pubsub.get_subscription(
                    PipelineConfigUpdateTopic,
                ),
                camera_output_pub=pubsub.get_publication_queue(
                    CameraNodeOutputTopic,
                ),
                timing_pub=pubsub.get_publication_queue(
                    PipelineTimingTopic,
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
            timing_pub: TopicPublicationQueue,
            shutdown_self_flag: Synchronized,
            camera_shm_dto: SharedMemoryRingBufferDTO,
            skeleton_inference_centralized: bool = False,
            log_pipeline_times: bool = False,
    ) -> None:
        import cv2
        from skellytracker.trackers.charuco_tracker.charuco_detector import CharucoDetector

        logger.debug(f"RealtimeCameraNode [{camera_id}] initializing")
        camera_shm = CameraSharedMemoryRingBuffer.recreate(
            dto=camera_shm_dto,
            read_only=False,
        )

        charuco_detector: CharucoDetector | None = None
        skeleton_detector: RTMPoseDetector | None = None
        # skeleton_detector: LegacyMediapipeDetector | None = None

        if config.charuco_tracking_enabled and config.charuco_detector_config is not None:
            charuco_detector = CharucoDetector.create(
                config=config.charuco_detector_config,
            )
        if (
                config.skeleton_tracking_enabled
                and config.skeleton_detector_config is not None
                and not skeleton_inference_centralized
        ):
            # In centralized GPU mode, the dedicated SkeletonInferenceNode owns
            # the ONNX session and serves all cameras via batched inference.
            # Skipping per-camera construction here is what avoids spawning
            # N independent CUDA contexts on a single GPU.
            # skeleton_detector = LegacyMediapipeDetector.create(
            #     config=config.skeleton_detector_config ,
            # )
            skeleton_detector = RTMPoseDetector.create(
                config=config.skeleton_detector_config,
            )

        frame_recarray: np.recarray | None = None
        timer = None
        if log_pipeline_times:
            timer = PipelineStageTimer(name=f"CameraNode-{camera_id}")

        try:
            logger.debug(f"RealtimeCameraNode [{camera_id}] entering main loop")
            while ipc.should_continue and not shutdown_self_flag.value:
                # ---- Handle config updates ----
                while True:
                    try:
                        update_msg: PipelineConfigUpdateMessage = pipeline_config_sub.get_nowait()
                    except queue.Empty:
                        break
                    new_config: CameraNodeConfig = update_msg.pipeline_config.camera_node_config
                    logger.debug(f"RealtimeCameraNode [{camera_id}] received config update")

                    if new_config.charuco_tracking_enabled and new_config.charuco_detector_config is not None:
                        charuco_detector = CharucoDetector.create(
                            config=new_config.charuco_detector_config,
                        )
                    elif not new_config.charuco_tracking_enabled:
                        charuco_detector = None

                    if (
                            new_config.skeleton_tracking_enabled
                            and new_config.skeleton_detector_config is not None
                            and not skeleton_inference_centralized
                    ):
                        skeleton_detector = RTMPoseDetector.create(
                            config=new_config.skeleton_detector_config,
                        )
                    elif not new_config.skeleton_tracking_enabled or skeleton_inference_centralized:
                        skeleton_detector = None

                    config = new_config

                # ---- Check shared memory validity every iteration ----
                if not camera_shm.valid:
                    logger.debug(
                        f"RealtimeCameraNode [{camera_id}] "
                        f"shared memory invalidated, exiting"
                    )
                    break

                # ---- Block until a frame request arrives (up to 5ms) ----
                # Replaces the busy-poll (empty() check + 1ms sleep) with an
                # efficient OS-level wait, cutting latency and CPU waste.
                try:
                    frame_msg: ProcessFrameNumberMessage = process_frame_number_sub.get(timeout=0.005)
                except queue.Empty:
                    continue
                frame_recarray = camera_shm.get_data_by_index(
                    index=frame_msg.frame_number,
                    rec_array=frame_recarray,
                )

                if frame_recarray.frame_metadata.camera_info.rotation != -1:
                    image = cv2.rotate(
                        src=frame_recarray.image[0],
                        rotateCode=frame_recarray.frame_metadata.camera_info.rotation[0]

                    )
                else:
                    image = frame_recarray.image[0]

                actual_frame_number: int = int(frame_recarray.frame_metadata.frame_number[0])
                actual_camera_id: CameraIdString = frame_recarray.frame_metadata.camera_info.camera_id[0]
                if actual_camera_id != camera_id:
                    raise RuntimeError(
                        f"RealtimeCameraNode [{camera_id}]: expected camera ID {camera_id} but got frame with camera ID {actual_camera_id}")
                if actual_frame_number != frame_msg.frame_number:
                    logger.warning(
                        f"RealtimeCameraNode [{camera_id}]: requested frame {frame_msg.frame_number} "
                        f"but ring buffer contained frame {actual_frame_number} — possible ring buffer overwrite"
                    )
                skeleton_observation = None
                charuco_observation = None
                t_frame_start = time.perf_counter() if timer is not None else 0.0
                if skeleton_detector is not None:
                    t0 = time.perf_counter() if timer is not None else 0.0
                    skeleton_observation = skeleton_detector.detect(
                        frame_number=actual_frame_number,
                        image=image,
                    )
                    if timer is not None:
                        timer.record("skeleton_detection", (time.perf_counter() - t0) * 1e3)
                if charuco_detector is not None:
                    t0 = time.perf_counter() if timer is not None else 0.0
                    charuco_observation = charuco_detector.detect(
                        frame_number=actual_frame_number,
                        image=image,
                    )
                    if timer is not None:
                        timer.record("charuco_detection", (time.perf_counter() - t0) * 1e3)
                if timer is not None:
                    timer.record("total_camera_node", (time.perf_counter() - t_frame_start) * 1e3)

                camera_output_pub.put(
                    CameraNodeOutputMessage(
                        camera_id=actual_camera_id,
                        frame_number=actual_frame_number,
                        charuco_observation=charuco_observation,
                        skeleton_observation=skeleton_observation,
                    ),
                )
                if timer is not None:
                    timer.maybe_flush(
                        publication_queue=timing_pub,
                        node_kind="camera",
                        camera_id=camera_id,
                    )

        except Exception as e:
            logger.exception(f"Exception in RealtimeCameraNode [{camera_id}]: {e}")
            ipc.kill_everything()
            raise
        finally:
            logger.debug(f"RealtimeCameraNode [{camera_id}] exiting")
