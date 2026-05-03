"""
RealtimeAggregationNode: collects per-camera observations for each frame,
triangulates mediapipe and charuco observations (if calibration is valid),
filters+constrains the triangulated skeleton via One Euro + FABRIK,
and publishes aggregated output.

Uses CalibrationStateTracker for graceful degradation: if triangulation fails
repeatedly, the calibration is invalidated and we continue publishing 2D-only
data until a new calibration file appears on disk.

Calibration hot-reload: the node polls the calibration file on disk once per
second. If the file has changed (e.g. after posthoc calibration completes),
the new calibration is loaded and the skeleton filter + velocity gate are reset.

Skeleton filtering (One Euro + FABRIK) runs on the triangulated 3D mediapipe
points. Bone lengths are estimated online from observed inter-keypoint distances
blended with an anthropometric prior. The filter resets on calibration reload
since the coordinate frame may change.
"""
import logging
import multiprocessing.synchronize
import os
import queue
import threading
import time
from dataclasses import dataclass
from multiprocessing.sharedctypes import Synchronized

import numpy as np
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import (
    CameraGroupSharedMemory,
    CameraGroupSharedMemoryDTO,
)
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, TopicSubscriptionQueue
from skellyforge.data_models.trajectory_3d import Point3d

from freemocap.core.pipeline.abcs.aggregator_node_abc import AggregatorNode
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.pipeline_stage_timer import PipelineStageTimer
from freemocap.core.pipeline.pipeline_timing_reporter import PipelineTimingReporter
from freemocap.core.tasks.calibration.shared.calibration_state import CalibrationStateTracker
from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.bone_length_estimator import AnthropometricPrior
from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.mediapipe_skeleton_config import \
    SkeletonDefinition
from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.realtime_point_gate import RealtimePointGate, \
    GateResult
from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.rigid_body_estimator import RigidBodyPose
from freemocap.core.tasks.mocap.skeleton_dewiggler.realtime_skeleton_filter import RealtimeFilterConfig, \
    RealtimeSkeletonFilter, FilterResult
from freemocap.core.pipeline.realtime.realtime_keypoint_filter import SimpleRealtimeKeypointFilter
from freemocap.core.types.type_overloads import TopicPublicationQueue
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import (
    CameraNodeOutputMessage,
    CameraNodeOutputTopic,
    PipelineConfigUpdateTopic,
    ProcessFrameNumberTopic,
    ProcessFrameNumberMessage,
    AggregationNodeOutputMessage,
    AggregationNodeOutputTopic,
    PipelineConfigUpdateMessage,
    SkeletonInferenceResultMessage,
    SkeletonInferenceResultTopic,
    PipelineTimingTopic,
)

# Cap on how many pending skeleton-inference results we hold while waiting for
# camera-node charuco outputs to arrive. Prevents unbounded memory growth if
# camera nodes lag (e.g. one camera unplugged). Older entries get dropped.
_MAX_PENDING_SKELETON_RESULTS: int = 2

logger = logging.getLogger(__name__)

# How often (seconds) to poll the calibration file for changes
CALIBRATION_POLL_INTERVAL_SECONDS: float = 1.0

# Skip Point3d Pydantic object creation when the binary keypoints path is
# active — the aggregator runs in a subprocess so it reads the env var here
# at import time, matching the flag check in realtime_pipeline.py.
_BINARY_KEYPOINTS_ENABLED: bool = os.environ.get("FREEMOCAP_BINARY_KEYPOINTS", "0") == "1"


def _merge_triangulated_arrays(
        *,
        triangulated: dict[str, np.ndarray] | None,
        into: dict[str, np.ndarray],
) -> None:
    """Merge triangulated 3D point arrays into the output dict, skipping NaN entries."""
    if triangulated is None:
        return
    for point_name, coords in triangulated.items():
        if not isinstance(coords, np.ndarray):
            raise TypeError(
                f"Unexpected type for triangulated point '{point_name}': "
                f"{type(coords).__name__} (expected np.ndarray)"
            )
        if np.any(np.isnan(coords)):
            continue
        into[point_name] = coords


def _arrays_to_point3d(arrays: dict[str, np.ndarray]) -> dict[str, Point3d]:
    """Convert dict of {name: ndarray(3,)} to dict of {name: Point3d}. Done once at the end."""
    return {
        name: Point3d(x=float(arr[0]), y=float(arr[1]), z=float(arr[2]))
        for name, arr in arrays.items()
    }


def _create_skeleton_filter(
        *,
        filter_config: RealtimeFilterConfig,
) -> RealtimeSkeletonFilter:
    """Create the skeleton filter with mediapipe body skeleton and anthropometric prior."""
    skeleton = SkeletonDefinition.mediapipe_body()
    prior = AnthropometricPrior.mediapipe_body()
    return RealtimeSkeletonFilter.create(
        skeleton=skeleton,
        prior=prior,
        config=filter_config,
    )


def _filter_skeleton_arrays(
        *,
        point_arrays: dict[str, np.ndarray],
        skeleton_filter: RealtimeSkeletonFilter,
        t: float,
) -> dict[str, np.ndarray]:
    """
    Run the skeleton filter on triangulated point arrays, returning filtered results.

    Operates entirely on dict[str, ndarray] — no Point3d conversion.
    """
    skeleton_keypoint_names = skeleton_filter.skeleton.keypoint_names

    skeleton_positions: dict[str, np.ndarray] = {
        name: arr for name, arr in point_arrays.items()
        if name in skeleton_keypoint_names
    }

    if not skeleton_positions:
        return point_arrays

    filter_result: FilterResult = skeleton_filter.process_frame(
        t=t,
        positions=skeleton_positions,
    )

    # Build output: filtered skeleton + unmodified non-skeleton points
    result: dict[str, np.ndarray] = {}
    for name, arr in point_arrays.items():
        if name in filter_result.positions:
            result[name] = filter_result.positions[name]
        else:
            result[name] = arr

    # Add predicted keypoints that weren't in this frame
    for name in filter_result.predicted_names:
        if name not in result and name in filter_result.positions:
            result[name] = filter_result.positions[name]

    return result


@dataclass
class RealtimeAggregatorNode(AggregatorNode):

    @classmethod
    def create(
            cls,
            *,
            config: RealtimePipelineConfig,
            camera_group_id: CameraGroupIdString,
            camera_ids: list[CameraIdString],
            worker_registry: WorkerRegistry,
            camera_group_shm_dto: CameraGroupSharedMemoryDTO,
            ipc: PipelineIPC,
            pubsub: PubSubTopicManager,
            result_ready_event: multiprocessing.synchronize.Event,
            result_consumed_event: multiprocessing.synchronize.Event,
    ) -> "RealtimeAggregatorNode":
        shutdown_self_flag, worker = cls._create_worker(
            target=cls._run,
            name=f"CameraGroup-{camera_group_id}-AggregationNode",
            worker_registry=worker_registry,
            log_queue=ipc.ws_queue,
            kwargs=dict(
                pipeline_config=config,
                camera_group_id=camera_group_id,
                camera_ids=camera_ids,
                ipc=ipc,
                camera_group_shm_dto=camera_group_shm_dto,
                camera_node_sub=pubsub.get_subscription(
                    CameraNodeOutputTopic,
                ),
                skeleton_inference_sub=pubsub.get_subscription(
                    SkeletonInferenceResultTopic,
                ),
                pipeline_config_sub=pubsub.get_subscription(
                    PipelineConfigUpdateTopic,
                ),
                process_frame_number_pub=pubsub.get_publication_queue(
                    ProcessFrameNumberTopic,
                ),
                aggregation_output_pub=pubsub.get_publication_queue(
                    AggregationNodeOutputTopic,
                ),
                timing_pub=pubsub.get_publication_queue(
                    PipelineTimingTopic,
                ),
                timing_sub=pubsub.get_subscription(
                    PipelineTimingTopic,
                ) if config.log_pipeline_times else None,
                result_ready_event=result_ready_event,
                result_consumed_event=result_consumed_event,
            ),
        )
        return cls(
            shutdown_self_flag=shutdown_self_flag,
            worker=worker,
        )

    @staticmethod
    def _run(
            *,
            pipeline_config: RealtimePipelineConfig,
            camera_group_id: CameraGroupIdString,
            camera_ids: list[CameraIdString],
            ipc: PipelineIPC,
            shutdown_self_flag: Synchronized,
            camera_group_shm_dto: CameraGroupSharedMemoryDTO,
            camera_node_sub: TopicSubscriptionQueue,
            skeleton_inference_sub: TopicSubscriptionQueue,
            pipeline_config_sub: TopicSubscriptionQueue,
            process_frame_number_pub: TopicPublicationQueue,
            aggregation_output_pub: TopicPublicationQueue,
            timing_pub: TopicPublicationQueue,
            timing_sub: TopicSubscriptionQueue | None,
            result_ready_event: multiprocessing.synchronize.Event,
            result_consumed_event: multiprocessing.synchronize.Event,
    ) -> None:
        logger.debug(f"RealtimeAggregationNode [{camera_group_id}] initializing")
        aggregator_config = pipeline_config.aggregator_config
        camera_group_shm = CameraGroupSharedMemory.recreate(
            shm_dto=camera_group_shm_dto,
            read_only=True,
        )
        calibration = CalibrationStateTracker.create_and_try_load()
        if calibration.is_valid:
            logger.info(
                f"RealtimeAggregationNode [{camera_group_id}] loaded calibration "
                f"from {calibration.calibration_path}"
            )
        else:
            logger.info(
                f"RealtimeAggregationNode [{camera_group_id}] starting without "
                f"calibration — triangulation disabled"
            )

        # Initialize skeleton filter for 3D smoothing + bone length constraint
        filter_config = aggregator_config.realtime_filter_config
        skeleton_filter = _create_skeleton_filter(filter_config=filter_config)

        # Initialize velocity gate for rejecting teleportation spikes
        point_gate = RealtimePointGate(
            max_velocity_m_per_s=filter_config.max_velocity_m_per_s,
            max_rejected_streak=filter_config.max_rejected_streak,
        )

        # Lightweight One Euro filter: smooths raw keypoints and gap-fills brief occlusions
        keypoint_filter = SimpleRealtimeKeypointFilter(
            min_cutoff=filter_config.min_cutoff,
            beta=filter_config.beta,
        )

        camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage | None] = {
            cam_id: None for cam_id in camera_ids
        }
        # Pending skeleton inference results keyed by frame_number. Populated
        # by the centralized SkeletonInferenceNode (when GPU mode is on);
        # consumed when the matching camera outputs arrive for that frame.
        pending_skeleton_results: dict[int, dict[CameraIdString, object | None]] = {}
        latest_requested_frame: int = -1
        last_received_frame: int = -1
        last_calibration_poll: float = time.monotonic()
        log_pipeline_times = pipeline_config.log_pipeline_times
        timer = PipelineStageTimer(name=f"AggregatorNode-{camera_group_id}") if log_pipeline_times else None
        t_frame_requested: float = time.perf_counter() if timer is not None else 0.0
        # Skip the first frame_collection_wait / loop_time samples — those
        # measure aggregator-startup → first-frame-arrival, which is dominated
        # by camera warmup (~5-7s) and is not a steady-state metric.
        recorded_first_frame: bool = False

        timing_reporter: PipelineTimingReporter | None = None
        timing_reporter_stop: threading.Event | None = None
        if log_pipeline_times and timing_sub is not None:
            timing_reporter_stop = threading.Event()
            timing_reporter = PipelineTimingReporter(
                name=str(camera_group_id),
                timing_sub=timing_sub,
                stop_event=timing_reporter_stop,
                expected_camera_count=len(camera_ids),
            )
            timing_reporter.start()

        try:
            previous_loop_tik = time.perf_counter() if timer is not None else 0.0
            logger.debug(f"RealtimeAggregationNode [{camera_group_id}] entering main loop")
            while ipc.should_continue and not shutdown_self_flag.value:
                # ---- Handle config updates ----
                while not pipeline_config_sub.empty():
                    msg: PipelineConfigUpdateMessage = pipeline_config_sub.get()
                    pipeline_config = msg.pipeline_config
                    aggregator_config = pipeline_config.aggregator_config
                    filter_config = aggregator_config.realtime_filter_config
                    logger.info(
                        f"RealtimeAggregationNode [{camera_group_id}] received config update"
                    )

                # ---- Periodically check if calibration file changed on disk ----
                now = time.monotonic()
                if now - last_calibration_poll >= CALIBRATION_POLL_INTERVAL_SECONDS:
                    last_calibration_poll = now
                    if calibration.check_for_update():
                        logger.info(
                            f"RealtimeAggregationNode [{camera_group_id}] "
                            f"hot-reloaded calibration from {calibration.calibration_path}"
                        )
                        # Coordinate frame may have changed — reset filter + gate
                        keypoint_filter.reset()
                        skeleton_filter.reset()
                        point_gate.reset()

                # ---- Request new frames if ready ----
                if not camera_group_shm.valid:
                    logger.debug(
                        f"RealtimeAggregationNode [{camera_group_id}] "
                        f"shared memory invalidated, exiting"
                    )
                    break
                current_multiframe_number = camera_group_shm.latest_multiframe_number
                # First-frame bootstrap and fallback. Normally, subsequent frames are
                # requested optimistically after camera collection completes (below).
                # This block handles startup (latest_requested_frame == -1) and the
                # rare case where the shm hadn't advanced at the optimistic-request point.
                if (current_multiframe_number > latest_requested_frame
                        and last_received_frame >= latest_requested_frame
                        and result_consumed_event.is_set()):
                    process_frame_number_pub.put(
                        ProcessFrameNumberMessage(
                            frame_number=current_multiframe_number,
                        ),
                    )
                    latest_requested_frame = current_multiframe_number
                    t_frame_requested = time.perf_counter() if timer is not None else 0.0

                # ---- Collect skeleton inference results (GPU mode) ----
                # Drained on every iteration so they're available whenever the
                # corresponding camera-node charuco outputs finish arriving.
                while not skeleton_inference_sub.empty():
                    skel_msg: SkeletonInferenceResultMessage = skeleton_inference_sub.get()
                    pending_skeleton_results[skel_msg.frame_number] = skel_msg.per_camera_skeleton
                # Bound the pending dict so a lagging camera can't grow it forever.
                if len(pending_skeleton_results) > _MAX_PENDING_SKELETON_RESULTS:
                    oldest = sorted(pending_skeleton_results.keys())[
                             :len(pending_skeleton_results) - _MAX_PENDING_SKELETON_RESULTS]
                    for k in oldest:
                        pending_skeleton_results.pop(k, None)

                # ---- Collect camera node outputs ----
                # If camera outputs are already complete (we looped back waiting
                # for the skeleton inference result), skip collection — the
                # existing entries are still valid and we just need the skeleton.
                all_cam_ready = all(
                    isinstance(v, CameraNodeOutputMessage)
                    for v in camera_node_outputs.values()
                )
                if not all_cam_ready:
                    # Block up to 5ms for the next camera output instead of
                    # busy-polling with empty() + 1ms sleep — cuts CPU waste
                    # and removes polling overhead from the critical path.
                    try:
                        cam_output: CameraNodeOutputMessage = camera_node_sub.get(timeout=0.005)
                    except queue.Empty:
                        continue
                    if cam_output.camera_id not in camera_ids:
                        raise ValueError(
                            f"Camera ID {cam_output.camera_id} not in "
                            f"camera IDs {list(camera_ids)}"
                        )
                    if cam_output.frame_number != latest_requested_frame:
                        raise RuntimeError(
                            f"WRONG FRAME from camera {cam_output.camera_id}: "
                            f"received frame {cam_output.frame_number} but expected "
                            f"{latest_requested_frame} (last_received={last_received_frame}). "
                            f"Camera processed the wrong frame — same frame sent twice?"
                        )
                    camera_node_outputs[cam_output.camera_id] = cam_output

                    if not all(
                            isinstance(v, CameraNodeOutputMessage)
                            for v in camera_node_outputs.values()
                    ):
                        continue

                # ---- In GPU mode, also wait for the skeleton inference result ----
                if (pipeline_config.use_centralized_gpu_inference
                        and pipeline_config.camera_node_config.skeleton_tracking_enabled):
                    expected_frame = next(iter(camera_node_outputs.values())).frame_number
                    if expected_frame not in pending_skeleton_results:
                        # Camera outputs are ready but skeleton inference hasn't
                        # caught up yet. Loop again — `camera_node_outputs` stays
                        # populated, and the skeleton result will land in the
                        # `skeleton_inference_sub` drain at the top of the next
                        # iteration.
                        continue
                    # Splice the per-camera skeletons into each CameraNodeOutputMessage
                    # so downstream triangulation code (which reads
                    # `output.skeleton_observation`) needs no changes.
                    skeleton_per_camera = pending_skeleton_results.pop(expected_frame)
                    for cam_id, output_msg in camera_node_outputs.items():
                        if output_msg is not None:
                            output_msg.skeleton_observation = skeleton_per_camera.get(cam_id)

                frame_numbers = [
                    msg.frame_number
                    for msg in camera_node_outputs.values()
                    if isinstance(msg, CameraNodeOutputMessage)
                ]
                if len(set(frame_numbers)) > 1:
                    logger.warning(
                        f"Frame number mismatch across cameras: {frame_numbers} "
                        f"(expected {latest_requested_frame})"
                    )

                last_received_frame = latest_requested_frame
                t_frame_start = time.perf_counter() if timer is not None else 0.0
                if timer is not None and recorded_first_frame:
                    timer.record("frame_collection_wait", (t_frame_start - t_frame_requested) * 1e3)

                # ---- Optimistically request next frame before aggregating ----
                # result_consumed_event is guaranteed set at this point: we checked it
                # before requesting this frame and haven't published a result yet.
                # Camera nodes start detecting frame N+1 while we triangulate/filter N.
                frame_n_outputs = camera_node_outputs
                camera_node_outputs = {cam_id: None for cam_id in camera_ids}
                latest_shm_frame = camera_group_shm.latest_multiframe_number
                if latest_shm_frame > latest_requested_frame:
                    process_frame_number_pub.put(
                        ProcessFrameNumberMessage(frame_number=latest_shm_frame)
                    )
                    latest_requested_frame = latest_shm_frame
                    t_frame_requested = time.perf_counter() if timer is not None else 0.0
                elif latest_shm_frame < latest_requested_frame:
                    raise RuntimeError(
                        f"SHM frame counter went backwards: latest_shm_frame={latest_shm_frame} "
                        f"< latest_requested_frame={latest_requested_frame}. "
                        f"Ring buffer should be monotonically increasing."
                    )

                # ---- Triangulate and process if calibration is valid ----
                # All processing stays in dict[str, ndarray] until final
                # conversion to Point3d for the output message.
                raw_keypoints: dict[str, np.ndarray] = {}
                filtered_keypoints: dict[str, np.ndarray] = {}
                skeleton_keypoints: dict[str, np.ndarray] = {}
                rigid_body_poses: dict[str, RigidBodyPose] = {}
                if calibration.is_valid and aggregator_config.triangulation_enabled:
                    # Triangulate mediapipe observations
                    skeleton_observations_by_camera = {
                        cam_id: output.skeleton_observation
                        for cam_id, output in frame_n_outputs.items()
                        if isinstance(output, CameraNodeOutputMessage)
                           and output.skeleton_observation is not None
                    }
                    if skeleton_observations_by_camera:
                        t0 = time.perf_counter() if timer is not None else 0.0
                        _merge_triangulated_arrays(
                            triangulated=calibration.try_angulate(
                                frame_number=last_received_frame,
                                frame_observations_by_camera=skeleton_observations_by_camera,
                                max_reprojection_error_px=filter_config.max_reprojection_error_px,
                                triangulation_config=aggregator_config.triangulation_config,
                            ),
                            into=raw_keypoints,
                        )
                        if timer is not None:
                            timer.record("skeleton_triangulation", (time.perf_counter() - t0) * 1e3)

                    # Triangulate charuco observations
                    charuco_observations_by_camera = {
                        cam_id: output.charuco_observation
                        for cam_id, output in frame_n_outputs.items()
                        if isinstance(output, CameraNodeOutputMessage)
                           and output.charuco_observation is not None
                    }
                    if charuco_observations_by_camera:
                        t0 = time.perf_counter() if timer is not None else 0.0
                        _merge_triangulated_arrays(
                            triangulated=calibration.try_angulate(
                                frame_number=last_received_frame,
                                frame_observations_by_camera=charuco_observations_by_camera,
                                max_reprojection_error_px=filter_config.max_reprojection_error_px,
                                triangulation_config=aggregator_config.triangulation_config,
                            ),
                            into=raw_keypoints,
                        )
                        if timer is not None:
                            timer.record("charuco_triangulation", (time.perf_counter() - t0) * 1e3)

                    # One Euro filter: smooth raw keypoints and gap-fill brief occlusions
                    if raw_keypoints:
                        t0 = time.perf_counter() if timer is not None else 0.0
                        filtered_keypoints = keypoint_filter.filter(
                            t=time.monotonic(),
                            raw_keypoints=raw_keypoints,
                        )
                        if timer is not None:
                            timer.record("keypoint_filter", (time.perf_counter() - t0) * 1e3)

                    # Velocity gate: reject teleportation spikes
                    if aggregator_config.filter_enabled:
                        if raw_keypoints:
                            t0 = time.perf_counter() if timer is not None else 0.0
                            gate_result: GateResult = point_gate.gate(
                                t=time.monotonic(),
                                points=raw_keypoints,
                            )
                            _merge_triangulated_arrays(
                                triangulated=gate_result.positions,
                                into=filtered_keypoints,
                            )
                            if timer is not None:
                                timer.record("velocity_gate", (time.perf_counter() - t0) * 1e3)

                        # Filter + constrain skeleton keypoints
                        if filtered_keypoints and aggregator_config.skeleton_enabled:
                            t0 = time.perf_counter() if timer is not None else 0.0
                            filtered_keypoints = _filter_skeleton_arrays(
                                point_arrays=filtered_keypoints,
                                skeleton_filter=skeleton_filter,
                                t=time.monotonic(),
                            )
                            if timer is not None:
                                timer.record("skeleton_filter", (time.perf_counter() - t0) * 1e3)

                    # # Estimate rigid body segment poses
                    # if filtered_keypoints and config.skeleton_enabled and skeleton_filter.current_bone_lengths:
                    #     skeleton_trajectories = estimate_rigid_bodies(
                    #         positions=filtered_keypoints,
                    #         skeleton=skeleton_filter.skeleton,
                    #         bone_lengths=skeleton_filter.current_bone_lengths,
                    #     )

                # Convert to Point3d once at the end for the output message
                if timer is not None:
                    timer.record("full_frame_processing", (time.perf_counter() - t_frame_start) * 1e3)
                    now = time.perf_counter()
                    if recorded_first_frame:
                        timer.record("loop_time", (now - previous_loop_tik) * 1e3)
                    previous_loop_tik = now
                    recorded_first_frame = True
                    timer.maybe_flush(
                        publication_queue=timing_pub,
                        node_kind="aggregator",
                    )

                # ---- Publish aggregated output ----
                aggregation_output_pub.put(
                    AggregationNodeOutputMessage(
                        frame_number=last_received_frame,
                        pipeline_id=ipc.pipeline_id,
                        pipeline_config=pipeline_config,
                        camera_group_id=camera_group_id,
                        camera_node_outputs=frame_n_outputs,
                        # When the binary path is active, skip the per-point
                        # Pydantic object creation — the raw arrays field is
                        # what the serializer actually reads.
                        keypoints_raw=(
                            {} if _BINARY_KEYPOINTS_ENABLED
                            else _arrays_to_point3d(raw_keypoints)
                        ),
                        keypoints_filtered=(
                            {} if _BINARY_KEYPOINTS_ENABLED
                            else _arrays_to_point3d(filtered_keypoints)
                        ),
                        keypoints_raw_arrays=raw_keypoints,
                        keypoints_filtered_arrays=filtered_keypoints,
                        # rigid_body_poses=rigid_body_poses,
                    ),
                )
                # Mark the slot as full and not-yet-consumed; the consumer
                # (websocket relay via RealtimePipeline.get_latest_frontend_payload)
                # flips these in the opposite order on grab.
                result_consumed_event.clear()
                result_ready_event.set()

        except Exception as e:
            logger.error(
                f"Exception in RealtimeAggregationNode [{camera_group_id}]: {e}",
                exc_info=True,
            )
            ipc.kill_everything()
            raise
        finally:
            if timing_reporter_stop is not None:
                timing_reporter_stop.set()
            if timing_reporter is not None:
                timing_reporter.join(timeout=2.0)
            logger.debug(f"RealtimeAggregationNode [{camera_group_id}] exiting")
