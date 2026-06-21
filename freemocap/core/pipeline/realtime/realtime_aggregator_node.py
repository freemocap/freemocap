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
import queue
import threading
import time
from dataclasses import dataclass
from multiprocessing.sharedctypes import Synchronized

import numpy as np
from freemocap.core.tasks.mocap.center_of_mass import (
    load_rtmpose_biomechanics,
    CenterOfMassResult,
    calculate_center_of_mass_per_frame,
    calculate_xcom,
)
from freemocap.core.tasks.mocap.realtime_skeleton_fitter import (
    RealtimeSkeletonFitter,
    SkeletonFittingResult,
)
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import (
    CameraGroupSharedMemory,
    CameraGroupSharedMemoryDTO,
)
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, TopicSubscriptionQueue
from skellyforge.data_models.trajectory_3d import Point3d

from freemocap.api.websocket.binary_keypoints_protocol import BINARY_KEYPOINTS_ENABLED
from freemocap.core.pipeline.abcs.aggregator_node_abc import AggregatorNode
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.pipeline_stage_timer import PipelineStageTimer
from freemocap.core.pipeline.pipeline_timing_reporter import PipelineTimingReporter
from freemocap.core.tasks.calibration.shared.calibration_state import CalibrationStateTracker
from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.realtime_point_gate import RealtimePointGate, \
    GateResult
from freemocap.core.tasks.mocap.skeleton_dewiggler.realtime_filter_config import RealtimeFilterConfig
from freemocap.core.pipeline.realtime.realtime_keypoint_filter import RealtimeKeypointFilter
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

        filter_config = aggregator_config.realtime_filter_config

        # Initialize velocity gate for rejecting teleportation spikes
        point_gate = RealtimePointGate(
            max_velocity_mm_per_s=filter_config.max_velocity_mm_per_s,
            max_rejected_streak=filter_config.max_rejected_streak,
        )

        # Load RTMPose body biomechanics for per-frame center of mass calculation.
        # Validated once at init via skellyforge's AnatomicalStructure — no Pydantic
        # in the hot loop.
        biomechanics = (
            load_rtmpose_biomechanics()
            if aggregator_config.center_of_mass_enabled
            else None
        )

        # Create skeleton fitter (canonical models + FABRIK trees + online
        # segment-length estimation).  Loaded once at init; per-frame hot
        # path is pure numpy + FABRIK.
        skeleton_fitter: RealtimeSkeletonFitter | None = None
        if aggregator_config.skeleton_fitting_enabled:
            skeleton_fitter = RealtimeSkeletonFitter.create(
                height_mm=filter_config.height_mm,
                fabrik_tolerance=filter_config.fabrik_tolerance,
                fabrik_max_iterations=filter_config.fabrik_max_iterations,
                integral_gain=filter_config.integral_gain,
                integral_leak=filter_config.integral_leak,
                max_integral_correction_mm=filter_config.max_integral_correction_mm,
                fabrik_refinement_passes=filter_config.fabrik_refinement_passes,
                fabrik_refinement_gain=filter_config.fabrik_refinement_gain,
                fabrik_jitter_mm=filter_config.fabrik_jitter_mm,
                max_welford_samples=filter_config.max_welford_samples,
            )
            logger.debug(
                f"RealtimeAggregationNode [{camera_group_id}] skeleton fitter created "
                f"(body bones: {len(skeleton_fitter._body_tree.bone_keys)}, "
                f"hand bones: {len(skeleton_fitter._hand_tree.bone_keys)})"
            )

        # One Euro filter: smooths raw keypoints and gap-fills brief occlusions
        keypoint_filter = RealtimeKeypointFilter(
            min_cutoff=filter_config.min_cutoff,
            beta=filter_config.beta,
            d_cutoff=filter_config.d_cutoff,
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
        last_calibration_poll: float = time.perf_counter()
        log_pipeline_times = pipeline_config.log_pipeline_times
        timer = PipelineStageTimer(name=f"AggregatorNode-{camera_group_id}") if log_pipeline_times else None
        t_frame_requested: float = time.perf_counter() if timer is not None else 0.0
        # Skip the first frame_collection_wait / loop_time samples — those
        # measure aggregator-startup → first-frame-arrival, which is dominated
        # by camera warmup (~5-7s) and is not a steady-state metric.
        recorded_first_frame: bool = False
        # XCoM velocity tracking: previous CoM position + timestamp for dt.
        prev_com: np.ndarray | None = None
        prev_com_time: float | None = None

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
                while True:
                    try:
                        msg: PipelineConfigUpdateMessage = pipeline_config_sub.get_nowait()
                    except queue.Empty:
                        break
                    pipeline_config = msg.pipeline_config
                    aggregator_config = pipeline_config.aggregator_config
                    filter_config = aggregator_config.realtime_filter_config
                    logger.info(
                        f"RealtimeAggregationNode [{camera_group_id}] received config update"
                    )

                # ---- Periodically check if calibration file changed on disk ----
                now = time.perf_counter()
                if now - last_calibration_poll >= CALIBRATION_POLL_INTERVAL_SECONDS:
                    last_calibration_poll = now
                    if calibration.check_for_update():
                        logger.info(
                            f"RealtimeAggregationNode [{camera_group_id}] "
                            f"hot-reloaded calibration from {calibration.calibration_path}"
                        )
                        # Coordinate frame may have changed — reset filter + gate + XCoM tracking
                        keypoint_filter.reset()
                        point_gate.reset()
                        prev_com = None
                        prev_com_time = None
                        # Rebuild skeleton fitter from scratch (segment-length
                        # stats are in the old coordinate frame)
                        if skeleton_fitter is not None:
                            skeleton_fitter = RealtimeSkeletonFitter.create(
                                height_mm=filter_config.height_mm,
                                fabrik_tolerance=filter_config.fabrik_tolerance,
                                fabrik_max_iterations=filter_config.fabrik_max_iterations,
                                integral_gain=filter_config.integral_gain,
                                integral_leak=filter_config.integral_leak,
                                max_integral_correction_mm=filter_config.max_integral_correction_mm,
                                fabrik_refinement_passes=filter_config.fabrik_refinement_passes,
                                fabrik_refinement_gain=filter_config.fabrik_refinement_gain,
                                fabrik_jitter_mm=filter_config.fabrik_jitter_mm,
                                max_welford_samples=filter_config.max_welford_samples,
                            )

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
                while True:
                    try:
                        skel_msg: SkeletonInferenceResultMessage = skeleton_inference_sub.get_nowait()
                    except queue.Empty:
                        break
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
                com_result: CenterOfMassResult | None = None
                xcom: Point3d | None = None
                fitted_result: SkeletonFittingResult | None = None
                if (calibration.is_valid or len(camera_ids) == 1) and aggregator_config.triangulation_enabled:
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
                            t=time.perf_counter(),
                            raw_keypoints=raw_keypoints,
                        )
                        if timer is not None:
                            timer.record("keypoint_filter", (time.perf_counter() - t0) * 1e3)

                    # Velocity gate: reject teleportation spikes
                    if aggregator_config.filter_enabled:
                        if raw_keypoints:
                            t0 = time.perf_counter() if timer is not None else 0.0
                            gate_result: GateResult = point_gate.gate(
                                t=time.perf_counter(),
                                points=raw_keypoints,
                            )
                            _merge_triangulated_arrays(
                                triangulated=gate_result.positions,
                                into=filtered_keypoints,
                            )
                            if timer is not None:
                                timer.record("velocity_gate", (time.perf_counter() - t0) * 1e3)

                    # ---- Skeleton fitting (canonical models + FABRIK) ----
                    if (
                        skeleton_fitter is not None
                        and filtered_keypoints
                    ):
                        t0 = time.perf_counter() if timer is not None else 0.0
                        fitted_result = skeleton_fitter.fit_frame(filtered_keypoints)
                        if timer is not None:
                            timer.record("skeleton_fitting", (time.perf_counter() - t0) * 1e3)

                    # ---- Center of mass ----
                    if (
                        biomechanics is not None
                        and filtered_keypoints
                        and aggregator_config.center_of_mass_enabled
                    ):
                        t0 = time.perf_counter() if timer is not None else 0.0
                        com_result = calculate_center_of_mass_per_frame(
                            keypoints=filtered_keypoints,
                            biomechanics=biomechanics,
                        )
                        if timer is not None:
                            timer.record("center_of_mass", (time.perf_counter() - t0) * 1e3)

                        # ---- XCoM (extrapolated center of mass) ----
                        # Inverted pendulum model requires CoM above ground plane.
                        # When the ground plane is a desk and the subject is
                        # sitting, CoM.z can be negative — the model doesn't
                        # apply, so we null XCoM until CoM goes positive again.
                        now_com = time.perf_counter()
                        com_z = float(com_result.total_body_com[2])
                        if (
                            com_z > 0.0
                            and prev_com is not None
                            and prev_com_time is not None
                        ):
                            dt = now_com - prev_com_time
                            if dt > 0:
                                xcom_arr = calculate_xcom(
                                    com=com_result.total_body_com,
                                    prev_com=prev_com,
                                    dt=dt,
                                )
                                xcom = Point3d(
                                    x=float(xcom_arr[0]),
                                    y=float(xcom_arr[1]),
                                    z=float(xcom_arr[2]),
                                )
                        prev_com = com_result.total_body_com.copy()
                        prev_com_time = now_com

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
                        keypoints=(
                            {} if BINARY_KEYPOINTS_ENABLED
                            else _arrays_to_point3d(filtered_keypoints)
                        ),
                        keypoints_arrays=filtered_keypoints,
                        center_of_mass_result=com_result,
                        xcom=xcom,
                        skeleton=(
                            {
                                **fitted_result.body_positions,
                                **fitted_result.left_hand_positions,
                                **fitted_result.right_hand_positions,
                            }
                            if fitted_result is not None
                            else None
                        ),
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
