"""Realtime frame-request adapter for the application inference service."""
from contextlib import ExitStack
import logging
import time
from dataclasses import dataclass
from multiprocessing.sharedctypes import Synchronized
from queue import Empty
from concurrent.futures import TimeoutError
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from freemocap.core.pipeline.inference_service import InferenceService, InferenceMode, InferenceRegistration, InferenceRequest
from freemocap.core.tracking.tracker_factory import tracker_session_requests, skeleton_tracker_config, mediapipe_tracker_config

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
from skellytracker.core.data_primitives.observation import Observation  # noqa: TC002

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
    """Thread adapter that submits live multiframes to shared inference."""

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
            inference_service: InferenceService,
    ) -> "RealtimeSkeletonInferenceNode":
        shutdown_self_flag, worker = cls._create_worker(
            owner_shutdown_flag=ipc.pipeline_shutdown_flag,
            worker_mode=WorkerMode.THREAD,
            target=cls._run,
            name=f"CameraGroup-{camera_group_id}-SkeletonInferenceNode",
            worker_registry=worker_registry,
            log_queue=ipc.ws_queue,
            kwargs=dict(
                inference_service=inference_service,
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
            inference_service: InferenceService,
    ) -> None:
        logger.debug(f"RealtimeSkeletonInferenceNode [{camera_group_id}] initializing")

        with ExitStack() as cleanup:
            camera_group_shm = CameraGroupSharedMemory.recreate(
                shm_dto=camera_group_shm_dto,
                read_only=True,
            )
            cleanup.callback(camera_group_shm.close)
            camera_shms: dict[CameraIdString, CameraSharedMemoryRingBuffer] = {
                camera_id: CameraSharedMemoryRingBuffer.recreate(
                    dto=camera_group_shm_dto.camera_shm_dtos[camera_id],
                    read_only=True,
                )
                for camera_id in camera_ids
            }

            for camera_shm in camera_shms.values():
                cleanup.callback(camera_shm.close)

            settings = pipeline_config.camera_node_config
            if settings.detector_type == "mediapipe":
                tracker_config = mediapipe_tracker_config(
                    model_complexity=settings.mediapipe_model_complexity,
                    detection_confidence=settings.mediapipe_detection_confidence,
                    presence_confidence=settings.mediapipe_presence_confidence,
                    tracking_confidence=settings.mediapipe_tracking_confidence,
                    num_hands=settings.mediapipe_num_hands, num_faces=settings.mediapipe_num_faces,
                )
            else:
                tracker_config = skeleton_tracker_config(model_name=settings.rtmpose_model_name,
                    confidence_threshold=settings.rtmpose_confidence_threshold,
                    video_fps=30.0, keypoint_bbox_expansion=0.05)
            client = inference_service.register(InferenceRegistration(
                pipeline_id=ipc.pipeline_id, mode=InferenceMode.REALTIME,
                tracker_config=tracker_config,
                sessions=tracker_session_requests(config=tracker_config, batch_size=len(camera_ids),
                    execution_provider=pipeline_config.skeleton_inference_node_config.execution_provider),
                shutdown_flag=ipc.pipeline_shutdown_flag,
            ))

            log_pipeline_times = pipeline_config.log_pipeline_times
            timer = (
                PipelineStageTimer(name=f"SkeletonInferenceNode-{camera_group_id}")
                if log_pipeline_times else None
            )

            frame_recarrays: dict[CameraIdString, np.recarray | None] = {
                cam_id: None for cam_id in camera_ids
            }

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
                    if not pipeline_config.camera_node_config.skeleton_tracking_enabled:
                        skeleton_result_pub.put(SkeletonInferenceResultMessage(
                            frame_number=requested_frame_number,
                            per_camera_skeleton={cam_id: None for cam_id in camera_ids},
                        ))
                        continue

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
                    result = client.submit(InferenceRequest(frame_number=requested_frame_number, images=images_dict))
                    while True:
                        try:
                            observations = result.result(timeout=0.05)
                            break
                        except TimeoutError:
                            if result.done():
                                raise
                            if not ipc.should_continue or shutdown_self_flag.value:
                                client.close()
                                return

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

                if client.failure is not None:
                    raise client.failure
            except Exception as e:
                logger.error(
                    f"Exception in RealtimeSkeletonInferenceNode [{camera_group_id}]: {e}",
                    exc_info=True,
                )
                ipc.shutdown_pipeline()
                raise
            finally:
                client.close()
                logger.debug(f"RealtimeSkeletonInferenceNode [{camera_group_id}] exiting")


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
            # Live buffers can advance while a request waits for inference.
            # Omit an unavailable frame rather than labeling another ordinal as it.
            continue

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
