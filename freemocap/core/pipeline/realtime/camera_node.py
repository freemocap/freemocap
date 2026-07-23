"""
RealtimeCameraNode: reads frames from shared memory, runs enabled trackers,
publishes CameraNodeOutputMessages.

Runs indefinitely until shutdown. Responds to pipeline config updates
(toggling trackers, changing charuco board params, etc).
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

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.abcs.source_node_abc import SourceNode
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.types.type_overloads import TopicPublicationQueue
from freemocap.core.pipeline.pipeline_stage_timer import PipelineStageTimer
from freemocap.core.pipeline.realtime.realtime_keypoint_filter import RealtimeKeypointFilter
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

logger = logging.getLogger(__name__)


def _build_charuco_tracker_from_config(node_config: CameraNodeConfig):
    """Return (Tracker, CpuSession) for charuco detection."""
    from skellytracker.core.detectors.keypoint_detectors.charuco import (
        CharucoDetectorConfig,
        CharucoBoardDefinition,
    )
    from freemocap.core.tracking.tracker_factory import build_charuco_tracker

    board_def = CharucoBoardDefinition.create_letter_size_5x3()
    for stage in node_config.charuco_tracker_config.stages:
        for kp_det in stage.keypoint_detectors:
            if isinstance(kp_det, CharucoDetectorConfig):
                board_def = kp_det.board
                break
    return build_charuco_tracker(board_def)


def _build_skeleton_tracker_from_config(node_config: CameraNodeConfig):
    """Return (Tracker, session) for skeleton detection in per-camera mode."""
    if node_config.detector_type == "mediapipe":
        from freemocap.core.tracking.tracker_factory import build_mediapipe_tracker
        return build_mediapipe_tracker(
            model_complexity=node_config.mediapipe_model_complexity,
            detection_confidence=node_config.mediapipe_detection_confidence,
            presence_confidence=node_config.mediapipe_presence_confidence,
            tracking_confidence=node_config.mediapipe_tracking_confidence,
            num_hands=node_config.mediapipe_num_hands,
            num_faces=node_config.mediapipe_num_faces,
        )

    from freemocap.core.tracking.tracker_factory import (
        build_skeleton_onnx_session,
        build_skeleton_tracker,
    )

    model_name = node_config.rtmpose_model_name
    confidence_threshold = node_config.rtmpose_confidence_threshold
    onnx_session = build_skeleton_onnx_session(batch_size=1, model_name=model_name)
    tracker = build_skeleton_tracker(
        onnx_session=onnx_session,
        model_name=model_name,
        confidence_threshold=confidence_threshold,
    )
    return tracker, onnx_session


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
        from skellytracker.core.tracker.tracker_state import TrackerState

        logger.debug(f"RealtimeCameraNode [{camera_id}] initializing")
        camera_shm = CameraSharedMemoryRingBuffer.recreate(
            dto=camera_shm_dto,
            read_only=False,
        )

        charuco_tracker = None
        charuco_session = None
        charuco_state = TrackerState()
        skeleton_tracker = None
        skeleton_session = None
        skeleton_state = TrackerState()

        if config.charuco_tracking_enabled and config.charuco_tracker_config is not None:
            charuco_tracker, charuco_session = _build_charuco_tracker_from_config(config)

        if (
                config.skeleton_tracking_enabled
                and config.skeleton_tracker_config is not None
                and not skeleton_inference_centralized
        ):
            # In centralized GPU mode, the dedicated SkeletonInferenceNode owns
            # the ONNX session and serves all cameras via batched inference.
            skeleton_tracker, skeleton_session = _build_skeleton_tracker_from_config(config)

        keypoint_filter: RealtimeKeypointFilter | None = None
        if config.enable_keypoint_filter:
            keypoint_filter = RealtimeKeypointFilter(
                dims=2,
                min_cutoff=config.keypoint_filter_min_cutoff,
                beta=config.keypoint_filter_beta,
                d_cutoff=config.keypoint_filter_d_cutoff,
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

                    if new_config.charuco_tracking_enabled and new_config.charuco_tracker_config is not None:
                        if charuco_tracker is not None:
                            charuco_tracker.close()
                        charuco_tracker, charuco_session = _build_charuco_tracker_from_config(new_config)
                        charuco_state = TrackerState()
                    elif not new_config.charuco_tracking_enabled:
                        if charuco_tracker is not None:
                            charuco_tracker.close()
                        charuco_tracker = None
                        charuco_session = None

                    if (
                            new_config.skeleton_tracking_enabled
                            and new_config.skeleton_tracker_config is not None
                            and not skeleton_inference_centralized
                    ):
                        if skeleton_tracker is not None:
                            skeleton_tracker.close()
                        skeleton_tracker, skeleton_session = _build_skeleton_tracker_from_config(new_config)
                        skeleton_state = TrackerState()
                    elif not new_config.skeleton_tracking_enabled or skeleton_inference_centralized:
                        if skeleton_tracker is not None:
                            skeleton_tracker.close()
                        skeleton_tracker = None
                        skeleton_session = None

                    if new_config.enable_keypoint_filter:
                        keypoint_filter = RealtimeKeypointFilter(
                            dims=2,
                            min_cutoff=new_config.keypoint_filter_min_cutoff,
                            beta=new_config.keypoint_filter_beta,
                            d_cutoff=new_config.keypoint_filter_d_cutoff,
                        )
                    else:
                        keypoint_filter = None

                    config = new_config

                # ---- Check shared memory validity every iteration ----
                if not camera_shm.valid:
                    logger.debug(
                        f"RealtimeCameraNode [{camera_id}] "
                        f"shared memory invalidated, exiting"
                    )
                    break

                # ---- Block until a frame request arrives (up to 5ms) ----
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
                        f"RealtimeCameraNode [{camera_id}]: expected camera ID {camera_id} "
                        f"but got frame with camera ID {actual_camera_id}"
                    )
                if actual_frame_number != frame_msg.frame_number:
                    logger.warning(
                        f"RealtimeCameraNode [{camera_id}]: requested frame {frame_msg.frame_number} "
                        f"but ring buffer contained frame {actual_frame_number} — possible ring buffer overwrite"
                    )
                skeleton_observation = None
                charuco_observation = None
                t_frame_start = time.perf_counter() if timer is not None else 0.0

                if skeleton_tracker is not None:
                    t0 = time.perf_counter() if timer is not None else 0.0
                    skeleton_observation, skeleton_state = skeleton_tracker.process_image(
                        image, actual_frame_number, skeleton_state
                    )
                    if timer is not None:
                        timer.record("skeleton_detection", (time.perf_counter() - t0) * 1e3)

                    body_stage = skeleton_observation.stages.get("body")
                    if body_stage is not None and body_stage.keypoints is not None:
                        # Apply 1€ filter to 2D keypoints before publishing.
                        if keypoint_filter is not None:
                            t0 = time.perf_counter() if timer is not None else 0.0
                            kpts = body_stage.keypoints
                            raw_2d = kpts.to_named_dict(dimensions=2)
                            filtered_2d = keypoint_filter.filter(
                                t=time.perf_counter(),
                                raw_keypoints=raw_2d,
                            )
                            xyz = kpts.xyz
                            for name, coords in filtered_2d.positions.items():
                                try:
                                    idx = kpts.index_of(name)
                                    xyz[idx, 0] = coords[0]
                                    xyz[idx, 1] = coords[1]
                                except KeyError:
                                    pass
                            if timer is not None:
                                timer.record("keypoint_filter_2d", (time.perf_counter() - t0) * 1e3)

                        # Confidence gating: NaN-out low-confidence 2D keypoints.
                        kpts = body_stage.keypoints
                        low_conf = kpts.visibility < config.confidence_threshold
                        if low_conf.any():
                            kpts.xyz[low_conf, :2] = np.nan
                            if timer is not None:
                                timer.record("confidence_gate_dropped", float(low_conf.sum()))

                if charuco_tracker is not None:
                    t0 = time.perf_counter() if timer is not None else 0.0
                    charuco_observation, charuco_state = charuco_tracker.process_image(
                        image, actual_frame_number, charuco_state
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
            if charuco_tracker is not None:
                charuco_tracker.close()
            if skeleton_tracker is not None:
                skeleton_tracker.close()
            logger.debug(f"RealtimeCameraNode [{camera_id}] exiting")
