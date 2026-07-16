"""
RealtimeSkeletonInferenceNode: dedicated GPU worker that owns one ONNX session
for skeleton detection and serves all cameras via batched inference.

Why this exists:
  Per-camera tracker construction (the legacy path) creates one CUDA context per
  camera process. On consumer Windows GPUs there is no cooperative context
  scheduling (no MPS), so N processes hammering one GPU serialize kernel-by-kernel
  and pay per-context overhead. This node centralizes inference: one CUDA context,
  one batched ONNX call per multi-camera frame.

Topology:
  - Subscribes to ProcessFrameNumberTopic (same trigger the camera nodes use).
  - Reads frame N's image directly from each camera's shared-memory ring buffer.
  - Calls tracker.process_batch(images_dict, ...) — one ORT call for all cameras.
  - Publishes a SkeletonInferenceResultMessage per frame with per-camera Observations.
  - The aggregator merges this with per-camera CameraNodeOutputMessage (charuco only
    in GPU mode) by frame_number.

Backpressure:
  Drains ProcessFrameNumberTopic to the latest message every iteration; older
  messages are dropped rather than queued. If the GPU falls behind the camera
  group's frame rate, we lose frames instead of accumulating lag.
"""
import gc
import logging
import time
from dataclasses import dataclass
from multiprocessing.sharedctypes import Synchronized
from queue import Empty

import cv2
import numpy as np
from numpy.typing import NDArray
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import (
    CameraGroupSharedMemory,
    CameraGroupSharedMemoryDTO,
)
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import (
    CameraSharedMemoryRingBuffer,
)
from skellycam.core.types.type_overloads import (
    CameraGroupIdString,
    CameraIdString,
    TopicSubscriptionQueue,
)
from skellycam.utilities.wait_functions import wait_1ms
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.tracker.tracker import Tracker
from skellytracker.core.tracker.tracker_state import TrackerState
from skellytracker.core.sessions.onnx_session import OnnxSession

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.abcs.source_node_abc import SourceNode
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.pipeline_stage_timer import PipelineStageTimer
from freemocap.core.types.type_overloads import TopicPublicationQueue
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import (
    PipelineConfigUpdateMessage,
    PipelineConfigUpdateTopic,
    ProcessFrameNumberMessage,
    ProcessFrameNumberTopic,
    SkeletonInferenceResultMessage,
    SkeletonInferenceResultTopic,
    PipelineTimingTopic,
)

logger = logging.getLogger(__name__)


@dataclass
class RealtimeSkeletonInferenceNode(SourceNode):
    """Worker node that hosts one batched OnnxSession for all cameras."""

    @classmethod
    def create(
            cls,
            *,
            camera_group_id: CameraGroupIdString,
            camera_ids: list[CameraIdString],
            worker_registry: WorkerRegistry,
            camera_group_shm_dto: CameraGroupSharedMemoryDTO,
            config: RealtimePipelineConfig,
            ipc: PipelineIPC,
            pubsub: PubSubTopicManager,
    ) -> "RealtimeSkeletonInferenceNode":
        shutdown_self_flag, worker = cls._create_worker(
            target=cls._run,
            name=f"CameraGroup-{camera_group_id}-SkeletonInferenceNode",
            worker_registry=worker_registry,
            log_queue=ipc.ws_queue,
            kwargs=dict(
                camera_group_id=camera_group_id,
                camera_ids=camera_ids,
                pipeline_config=config,
                ipc=ipc,
                camera_group_shm_dto=camera_group_shm_dto,
                process_frame_number_sub=pubsub.get_subscription(ProcessFrameNumberTopic),
                pipeline_config_sub=pubsub.get_subscription(PipelineConfigUpdateTopic),
                skeleton_result_pub=pubsub.get_publication_queue(SkeletonInferenceResultTopic),
                timing_pub=pubsub.get_publication_queue(PipelineTimingTopic),
            ),
        )
        return cls(
            shutdown_self_flag=shutdown_self_flag,
            worker=worker,
        )

    @staticmethod
    def _run(
            *,
            camera_group_id: CameraGroupIdString,
            camera_ids: list[CameraIdString],
            pipeline_config: RealtimePipelineConfig,
            ipc: PipelineIPC,
            shutdown_self_flag: Synchronized,
            camera_group_shm_dto: CameraGroupSharedMemoryDTO,
            process_frame_number_sub: TopicSubscriptionQueue,
            pipeline_config_sub: TopicSubscriptionQueue,
            skeleton_result_pub: TopicPublicationQueue,
            timing_pub: TopicPublicationQueue,
    ) -> None:
        logger.debug(f"RealtimeSkeletonInferenceNode [{camera_group_id}] initializing")

        camera_group_shm = CameraGroupSharedMemory.recreate(
            shm_dto=camera_group_shm_dto,
            read_only=True,
        )
        camera_shms: dict[CameraIdString, CameraSharedMemoryRingBuffer] = {
            camera_id: CameraSharedMemoryRingBuffer.recreate(
                dto=camera_group_shm_dto.camera_shm_dtos[camera_id],
                read_only=True,
            )
            for camera_id in camera_ids
        }

        tracker, onnx_session = _build_session_and_tracker(pipeline_config, num_cameras=len(camera_ids))
        if tracker is None:
            logger.error(
                f"RealtimeSkeletonInferenceNode [{camera_group_id}] could not "
                f"construct tracker/session; exiting."
            )
            ipc.kill_everything()
            return

        log_pipeline_times = pipeline_config.log_pipeline_times
        timer = (
            PipelineStageTimer(name=f"SkeletonInferenceNode-{camera_group_id}")
            if log_pipeline_times else None
        )
        _MAX_SESSION_RESTARTS = 3
        session_restart_count = 0

        frame_recarrays: dict[CameraIdString, np.recarray | None] = {
            cam_id: None for cam_id in camera_ids
        }
        # Per-camera temporal state; empty dict means first frame auto-inits.
        tracker_states: dict[CameraIdString, TrackerState] = {}

        try:
            logger.debug(
                f"RealtimeSkeletonInferenceNode [{camera_group_id}] entering main loop"
            )
            while ipc.should_continue and not shutdown_self_flag.value:
                wait_1ms()

                # ---- Handle config updates ----
                while True:
                    try:
                        msg: PipelineConfigUpdateMessage = pipeline_config_sub.get_nowait()
                    except Empty:
                        break
                    pipeline_config = msg.pipeline_config
                    logger.debug(
                        f"RealtimeSkeletonInferenceNode [{camera_group_id}] "
                        f"received config update (session changes require pipeline restart)"
                    )

                # ---- Drain to latest frame number (drop stale) ----
                latest_frame_msg: ProcessFrameNumberMessage | None = None
                dropped_count = 0
                while True:
                    try:
                        candidate = process_frame_number_sub.get_nowait()
                    except Empty:
                        break
                    if latest_frame_msg is not None:
                        dropped_count += 1
                    latest_frame_msg = candidate
                if latest_frame_msg is None:
                    continue
                if dropped_count and timer is not None:
                    timer.record("dropped_frames", float(dropped_count))

                if not camera_group_shm.valid:
                    logger.debug(
                        f"RealtimeSkeletonInferenceNode [{camera_group_id}] "
                        f"shared memory invalidated, exiting"
                    )
                    break

                requested_frame_number = latest_frame_msg.frame_number

                # ---- Read N images from per-camera ring buffers ----
                t_read = time.perf_counter() if timer is not None else 0.0
                images, ordered_camera_ids = _read_frames(
                    camera_ids=camera_ids,
                    camera_shms=camera_shms,
                    frame_recarrays=frame_recarrays,
                    requested_frame_number=requested_frame_number,
                )
                if timer is not None:
                    timer.record("frame_read", (time.perf_counter() - t_read) * 1e3)

                if not images:
                    skeleton_result_pub.put(
                        SkeletonInferenceResultMessage(
                            frame_number=requested_frame_number,
                            per_camera_skeleton={cam_id: None for cam_id in camera_ids},
                        ),
                    )
                    continue

                # ---- Batched skeleton inference ----
                t_inf = time.perf_counter() if timer is not None else 0.0
                images_dict = {
                    cam_id: img
                    for cam_id, img in zip(ordered_camera_ids, images)
                }
                try:
                    observations, tracker_states = tracker.process_batch(
                        images_dict, requested_frame_number, tracker_states
                    )
                except Exception as mem_err:
                    if not (
                        isinstance(mem_err, MemoryError)
                        or "BFCArena" in str(mem_err)
                        or "Available memory" in str(mem_err)
                    ):
                        raise
                    logger.error(
                        f"RealtimeSkeletonInferenceNode [{camera_group_id}] GPU OOM during "
                        f"inference (restart {session_restart_count + 1}/{_MAX_SESSION_RESTARTS}): "
                        f"{mem_err}"
                    )
                    if session_restart_count >= _MAX_SESSION_RESTARTS:
                        logger.error(
                            f"RealtimeSkeletonInferenceNode [{camera_group_id}] exceeded max "
                            f"session restarts — giving up."
                        )
                        ipc.kill_everything()
                        return
                    tracker.close()
                    gc.collect()
                    tracker, onnx_session = _build_session_and_tracker(pipeline_config, num_cameras=len(camera_ids))
                    if tracker is None:
                        logger.error(
                            f"RealtimeSkeletonInferenceNode [{camera_group_id}] failed to rebuild "
                            f"tracker after MemoryError — giving up."
                        )
                        ipc.kill_everything()
                        return
                    tracker_states = {}
                    session_restart_count += 1
                    logger.info(
                        f"RealtimeSkeletonInferenceNode [{camera_group_id}] tracker rebuilt "
                        f"successfully after MemoryError."
                    )
                    continue

                if timer is not None:
                    inf_ms = (time.perf_counter() - t_inf) * 1e3
                    timer.record("predict_batch", inf_ms)
                    timer.record("predict_per_camera", inf_ms / max(len(images), 1))

                # ---- Apply confidence gating per camera ----
                conf_threshold = pipeline_config.camera_node_config.confidence_threshold
                per_camera_skeleton: dict[CameraIdString, Observation | None] = {}
                for camera_id, obs in observations.items():
                    body_stage = obs.stages.get("body")
                    if body_stage is not None and body_stage.keypoints is not None:
                        kpts = body_stage.keypoints
                        low_conf = kpts.visibility < conf_threshold
                        if low_conf.any():
                            kpts.xyz[low_conf, :2] = np.nan
                    per_camera_skeleton[camera_id] = obs

                # Cameras whose frame we couldn't read get None.
                for camera_id in camera_ids:
                    per_camera_skeleton.setdefault(camera_id, None)

                skeleton_result_pub.put(
                    SkeletonInferenceResultMessage(
                        frame_number=requested_frame_number,
                        per_camera_skeleton=per_camera_skeleton,
                    ),
                )
                if timer is not None:
                    timer.maybe_flush(
                        publication_queue=timing_pub,
                        node_kind="skeleton_inference",
                    )

        except Exception as e:
            logger.error(
                f"Exception in RealtimeSkeletonInferenceNode [{camera_group_id}]: {e}",
                exc_info=True,
            )
            ipc.kill_everything()
            raise
        finally:
            if tracker is not None:
                tracker.close()
            logger.debug(f"RealtimeSkeletonInferenceNode [{camera_group_id}] exiting")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_session_and_tracker(
    pipeline_config: RealtimePipelineConfig,
    num_cameras: int = 1,
) -> tuple[Tracker | None, OnnxSession | None]:
    """Construct the OnnxSession and Tracker from the pipeline config.

    Returns (None, None) on failure — caller should treat this as fatal in
    centralized GPU mode.
    """
    from freemocap.core.tracking.tracker_factory import (
        build_skeleton_onnx_session,
        build_skeleton_tracker,
    )
    from skellytracker.core.detectors.keypoint_detectors.rtmpose import RTMPoseDetectorConfig

    skel_tracker_config = pipeline_config.camera_node_config.skeleton_tracker_config
    inf_config = pipeline_config.skeleton_inference_node_config

    # Extract model name from the tracker config.
    model_name = "rtmw-x-l_256x192"
    if skel_tracker_config is not None:
        for stage in skel_tracker_config.stages:
            for kp_det in stage.keypoint_detectors:
                if isinstance(kp_det, RTMPoseDetectorConfig):
                    model_name = kp_det.model_name
                    break

    try:
        batch_size = min(inf_config.max_batch_size, num_cameras)
        onnx_session = build_skeleton_onnx_session(
            batch_size=batch_size,
            execution_provider=inf_config.execution_provider,
            model_name=model_name,
        )
        tracker = build_skeleton_tracker(
            onnx_session=onnx_session,
            model_name=model_name,
        )
        return tracker, onnx_session
    except Exception as e:
        logger.error(
            f"Failed to construct OnnxSession/Tracker with provider="
            f"{inf_config.execution_provider!r}: {e!r}",
            exc_info=True,
        )
        return None, None


def _read_frames(
        *,
        camera_ids: list[CameraIdString],
        camera_shms: dict[CameraIdString, CameraSharedMemoryRingBuffer],
        frame_recarrays: dict[CameraIdString, np.recarray | None],
        requested_frame_number: int,
) -> tuple[list[NDArray[np.uint8]], list[CameraIdString]]:
    """Read frame `requested_frame_number` from each camera's ring buffer."""
    images: list[NDArray[np.uint8]] = []
    ordered_camera_ids: list[CameraIdString] = []

    for camera_id in camera_ids:
        camera_shm = camera_shms[camera_id]
        try:
            frame_recarray = camera_shm.get_data_by_index(
                index=requested_frame_number,
                rec_array=frame_recarrays[camera_id],
            )
        except Exception as e:
            logger.debug(
                f"Could not read frame {requested_frame_number} from camera "
                f"{camera_id}: {e!r}"
            )
            continue
        frame_recarrays[camera_id] = frame_recarray

        actual_frame_number = int(frame_recarray.frame_metadata.frame_number[0])
        if actual_frame_number != requested_frame_number:
            logger.warning(
                f"SkeletonInferenceNode: requested frame {requested_frame_number} "
                f"from camera {camera_id} but got {actual_frame_number} — "
                f"ring buffer advanced; using available frame."
            )

        rotation = frame_recarray.frame_metadata.camera_info.rotation
        if rotation != -1:
            image = cv2.rotate(
                src=frame_recarray.image[0],
                rotateCode=rotation[0],
            )
        else:
            image = frame_recarray.image[0]

        images.append(image)
        ordered_camera_ids.append(camera_id)

    return images, ordered_camera_ids
