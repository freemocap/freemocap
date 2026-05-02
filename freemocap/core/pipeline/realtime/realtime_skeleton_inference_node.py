"""
RealtimeSkeletonInferenceNode: dedicated GPU worker that owns one ONNX session
for skeleton detection and serves all cameras via batched inference.

Why this exists:
  Per-camera RTMPoseDetector construction (the legacy path) creates one CUDA
  context per camera process. On consumer Windows GPUs there is no cooperative
  context scheduling (no MPS), so N processes hammering one GPU serialize
  kernel-by-kernel and pay per-context overhead. This node centralizes
  inference: one CUDA context, one batched ONNX call per multi-camera frame.

Topology:
  - Subscribes to ProcessFrameNumberTopic (the same topic the camera nodes
    use as their "process frame N" trigger).
  - Reads frame N's image directly from each camera's shared-memory ring buffer
    (the same DTO the aggregator already gets).
  - Calls RTMPoseSession.predict_batch(images) — one session.run for all cameras.
  - Publishes a single SkeletonInferenceResultMessage per frame, keyed by
    frame_number, with per-camera RTMPoseObservation.
  - The aggregator merges this with per-camera CameraNodeOutputMessage
    (charuco-only in GPU mode) by frame_number.

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
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation
from skellytracker.trackers.rtmpose_tracker.rtmpose_detector import RTMPoseDetectorConfig
from skellytracker.trackers.rtmpose_tracker.rtmpose_observation import RTMPoseObservation
from skellytracker.trackers.rtmpose_tracker.rtmpose_session import (
    RTMPoseSession,
    RTMPoseSessionConfig,
)

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
)

logger = logging.getLogger(__name__)


@dataclass
class RealtimeSkeletonInferenceNode(SourceNode):
    """Worker node that hosts one batched RTMPoseSession for all cameras."""

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
    ) -> None:
        logger.debug(f"RealtimeSkeletonInferenceNode [{camera_group_id}] initializing")

        camera_group_shm = CameraGroupSharedMemory.recreate(
            shm_dto=camera_group_shm_dto,
            read_only=True,
        )
        # Per-camera ring buffer handles for direct image reads. We mirror
        # `camera_node.py`'s recreate call but read-only since this worker
        # never writes frames.
        camera_shms: dict[CameraIdString, CameraSharedMemoryRingBuffer] = {
            camera_id: CameraSharedMemoryRingBuffer.recreate(
                dto=camera_group_shm_dto.camera_shm_dtos[camera_id],
                read_only=True,
            )
            for camera_id in camera_ids
        }

        session = _build_session(pipeline_config)
        if session is None:
            logger.error(
                f"RealtimeSkeletonInferenceNode [{camera_group_id}] could not "
                f"construct RTMPoseSession; exiting."
            )
            ipc.kill_everything()
            return

        log_pipeline_times = pipeline_config.log_pipeline_times
        timer = PipelineStageTimer(name=f"SkeletonInferenceNode-{camera_group_id}") if log_pipeline_times else None
        _MAX_SESSION_RESTARTS = 3
        session_restart_count = 0
        # Per-camera scratch recarrays (avoids reallocating each frame).
        frame_recarrays: dict[CameraIdString, np.recarray | None] = {
            cam_id: None for cam_id in camera_ids
        }

        try:
            logger.debug(
                f"RealtimeSkeletonInferenceNode [{camera_group_id}] entering main loop "
                f"(active_provider={session.active_provider!r})"
            )
            while ipc.should_continue and not shutdown_self_flag.value:
                wait_1ms()

                # ---- Handle config updates (only act on flips that change session shape) ----
                while not pipeline_config_sub.empty():
                    msg: PipelineConfigUpdateMessage = pipeline_config_sub.get()
                    pipeline_config = msg.pipeline_config
                    logger.debug(
                        f"RealtimeSkeletonInferenceNode [{camera_group_id}] "
                        f"received config update (no hot-reload of session; "
                        f"changes to detector mode require a pipeline restart)"
                    )

                # ---- Drain to latest frame number (drop stale) ----
                latest_frame_msg: ProcessFrameNumberMessage | None = None
                dropped_count = 0
                while not process_frame_number_sub.empty():
                    candidate = process_frame_number_sub.get()
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
                    # Ring buffer didn't have the frame for any camera; skip.
                    continue

                # ---- Batched skeleton inference ----
                t_inf = time.perf_counter() if timer is not None else 0.0
                try:
                    batch_results = session.predict_batch(images)
                except MemoryError as mem_err:
                    logger.error(
                        f"RealtimeSkeletonInferenceNode [{camera_group_id}] MemoryError during "
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
                    del session
                    gc.collect()
                    session = _build_session(pipeline_config)
                    if session is None:
                        logger.error(
                            f"RealtimeSkeletonInferenceNode [{camera_group_id}] failed to rebuild "
                            f"session after MemoryError — giving up."
                        )
                        ipc.kill_everything()
                        return
                    session_restart_count += 1
                    logger.info(
                        f"RealtimeSkeletonInferenceNode [{camera_group_id}] session rebuilt "
                        f"successfully after MemoryError."
                    )
                    continue  # skip this frame, resume on next
                if timer is not None:
                    inf_ms = (time.perf_counter() - t_inf) * 1e3
                    timer.record("predict_batch", inf_ms)
                    # Per-camera-equivalent latency, for comparing with the legacy
                    # per-camera `skeleton_detection` timer in camera_node logs.
                    timer.record("predict_per_camera", inf_ms / max(len(images), 1))

                # ---- Build per-camera observations ----
                per_camera_skeleton: dict[CameraIdString, BaseObservation | None] = {}
                for camera_id, image, (keypoints, scores) in zip(
                        ordered_camera_ids, images, batch_results,
                ):
                    per_camera_skeleton[camera_id] = RTMPoseObservation.from_detection_results(
                        frame_number=requested_frame_number,
                        keypoints=keypoints,
                        scores=scores,
                        image_size=(int(image.shape[0]), int(image.shape[1])),
                    )
                # Cameras whose frame we couldn't read get None — aggregator
                # treats this as "no skeleton this frame for this camera"
                # (same semantics as today's missing-detection path).
                for camera_id in camera_ids:
                    per_camera_skeleton.setdefault(camera_id, None)

                skeleton_result_pub.put(
                    SkeletonInferenceResultMessage(
                        frame_number=requested_frame_number,
                        per_camera_skeleton=per_camera_skeleton,
                    ),
                )
                if timer is not None:
                    timer.maybe_report()

        except Exception as e:
            logger.error(
                f"Exception in RealtimeSkeletonInferenceNode [{camera_group_id}]: {e}",
                exc_info=True,
            )
            ipc.kill_everything()
            raise
        finally:
            logger.debug(f"RealtimeSkeletonInferenceNode [{camera_group_id}] exiting")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_session(pipeline_config: RealtimePipelineConfig) -> RTMPoseSession | None:
    """Construct the centralized RTMPoseSession from the pipeline config.

    Reads model size / mode from `camera_node_config.skeleton_detector_config`
    so a single source of truth governs which model is used in either pipeline
    mode. Reads provider / cache settings from `skeleton_inference_node_config`.
    Returns None if the skeleton detector isn't an RTMPose config (caller
    should treat this as a fatal misconfiguration in GPU mode).
    """
    skel_config = pipeline_config.camera_node_config.skeleton_detector_config
    if not isinstance(skel_config, RTMPoseDetectorConfig):
        logger.warning(
            f"Centralized GPU inference is enabled but the skeleton detector "
            f"config is not RTMPoseDetectorConfig (got {type(skel_config).__name__}). "
            f"Falling back to legacy per-camera inference."
        )
        return None

    inf_config = pipeline_config.skeleton_inference_node_config
    #TODO - this is dumb, I think? WE should be able to just use the inference node config directly  without this nonsense?

    # Pick mode safely. RTMPoseSessionConfig accepts a Literal of three values;
    # other strings (e.g. legacy values) get coerced to "balanced" rather than
    # failing pydantic validation — keeps the pipeline alive on weird configs.
    mode = skel_config.mode if skel_config.mode in ("performance", "lightweight", "balanced") else "balanced"

    session_config = RTMPoseSessionConfig(
        mode=mode,
        execution_provider=inf_config.execution_provider,
        engine_cache_dir=inf_config.engine_cache_dir,
        max_batch_size=inf_config.max_batch_size,
        on_provider_missing="fallback" if inf_config.fallback_on_missing_provider else "raise",
    )

    try:
        return RTMPoseSession.create(session_config)
    except Exception as e:
        logger.error(
            f"Failed to construct RTMPoseSession with provider={inf_config.execution_provider!r}: {e!r}",
            exc_info=True,
        )
        return None


def _read_frames(
        *,
        camera_ids: list[CameraIdString],
        camera_shms: dict[CameraIdString, CameraSharedMemoryRingBuffer],
        frame_recarrays: dict[CameraIdString, np.recarray | None],
        requested_frame_number: int,
) -> tuple[list[NDArray[np.uint8]], list[CameraIdString]]:
    """Read frame `requested_frame_number` from each camera's ring buffer.

    Returns parallel lists `(images, camera_ids)` for the cameras whose ring
    buffer actually contained the requested frame. Cameras whose buffer was
    overwritten or whose frame metadata mismatched are silently skipped (the
    aggregator already tolerates missing per-camera observations on a frame).

    Mirrors the rotation-handling logic from `camera_node.py:171-178` so the
    image fed to ONNX is identical to what the legacy per-camera path would
    have inferred over.
    """
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
            # Ring buffer has moved on — use the frame that's actually there
            # rather than dropping the camera entirely.
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
