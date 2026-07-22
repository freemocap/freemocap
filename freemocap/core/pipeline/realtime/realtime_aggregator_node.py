"""
RealtimeAggregationNode: collects per-camera observations for each frame,
triangulates mediapipe and charuco observations (if calibration is valid),
filters the triangulated skeleton (One Euro smoothing + velocity gate) and
corrects it to rigid bone lengths, then publishes aggregated output.

Uses CalibrationStateTracker for graceful degradation: if triangulation fails
repeatedly, the calibration is invalidated and we continue publishing 2D-only
data until a new calibration file appears on disk.

Calibration hot-reload: the node polls the calibration file on disk once per
second. If the file has changed (e.g. after posthoc calibration completes),
the new calibration is loaded and the skeleton filter + velocity gate are reset.

Rigid-body correction (``RealtimeSkeletonRigidifier``) runs on the triangulated
3D points: each bone's length is estimated online (a best-K-by-reprojection-error
median, seeded from anthropometry and bounded to a trust region around the seed)
and enforced by a single closed-form forward pass. Only real (non-extrapolated)
keypoints teach lengths. The reset signal arms a calibration ritual — countdown,
quality-gated capture, freeze — instead of re-fitting on the next frame; the
ritual state is published every frame on SkeletonFitStateTopic.
"""
import logging
import multiprocessing.synchronize
import queue
import threading
import time
from dataclasses import dataclass
from multiprocessing.sharedctypes import Synchronized
from pathlib import Path

import numpy as np
from freemocap.core.tasks.mocap.center_of_mass import (
    load_body_biomechanics,
    CenterOfMassResult,
    calculate_center_of_mass_per_frame,
    calculate_center_of_mass_from_canonical,
    calculate_xcom,
)
from freemocap.core.kinematics.online.streaming_kinematics import StreamingKinematics
from freemocap.core.kinematics.segment_lengths import (
    DEFAULT_DIAGNOSTIC_INTERVAL,
    StreamingSegmentLengthMonitor,
)
from freemocap.core.tasks.mocap.rigid_body.skeleton_rigidifier import (
    RealtimeSkeletonRigidifier,
    RigidifyResult,
)
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
from freemocap.core.tasks.triangulation.helpers.angulation_result import AngulationResult
from freemocap.core.tasks.mocap.realtime_filtering.realtime_point_gate import RealtimePointGate, \
    GateResult
from freemocap.core.tasks.mocap.realtime_filtering.realtime_filter_config import RealtimeFilterConfig
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
    SkeletonFitStateMessage,
    SkeletonFitStateTopic,
)

# Cap on how many pending skeleton-inference results we hold while waiting for
# camera-node charuco outputs to arrive. Prevents unbounded memory growth if
# camera nodes lag (e.g. one camera unplugged). Older entries get dropped.
_MAX_PENDING_SKELETON_RESULTS: int = 2

# Max time to wait for a specific frame's skeleton-inference result before
# giving up on it and proceeding without a skeleton for that frame. Without
# this, a SkeletonInferenceNode restart (e.g. detector swap) orphans whatever
# frame request the old node's process was mid-flight on — its pub/sub
# subscription dies with it and the new node's subscription only sees
# requests published after it was created — so waiting unconditionally here
# would deadlock the whole pipeline (camera feed included) forever.
_SKELETON_RESULT_WAIT_TIMEOUT_SECONDS: float = 2.0

logger = logging.getLogger(__name__)

# How often (seconds) to poll the calibration file for changes
CALIBRATION_POLL_INTERVAL_SECONDS: float = 1.0

def _merge_angulation(
        *,
        angulation: AngulationResult | None,
        into_points: dict[str, np.ndarray],
        into_errors: dict[str, float],
) -> None:
    """Merge one frame's triangulated points and their reprojection errors into
    the output dicts, skipping NaN entries. Error-less results (single-camera
    planar projection) merge points only."""
    if angulation is None:
        return
    for point_name, coords in angulation.points.items():
        if not isinstance(coords, np.ndarray):
            raise TypeError(
                f"Unexpected type for triangulated point '{point_name}': "
                f"{type(coords).__name__} (expected np.ndarray)"
            )
        if np.any(np.isnan(coords)):
            continue
        into_points[point_name] = coords
        if angulation.errors_px is not None and point_name in angulation.errors_px:
            into_errors[point_name] = angulation.errors_px[point_name]


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
            skeleton_fitter_reset_sub: TopicSubscriptionQueue,
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
                skeleton_fitter_reset_sub=skeleton_fitter_reset_sub,
                skeleton_fit_state_pub=pubsub.get_publication_queue(
                    SkeletonFitStateTopic,
                ),
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
            skeleton_fitter_reset_sub: TopicSubscriptionQueue,
            skeleton_fit_state_pub: TopicPublicationQueue,
    ) -> None:
        logger.debug(f"RealtimeAggregationNode [{camera_group_id}] initializing")
        aggregator_config = pipeline_config.aggregator_config
        camera_group_shm = CameraGroupSharedMemory.recreate(
            shm_dto=camera_group_shm_dto,
            read_only=True,
        )
        _configured_calib_path = aggregator_config.calibration_toml_path
        calibration = CalibrationStateTracker.create_and_try_load(
            calibration_toml_path=Path(_configured_calib_path) if _configured_calib_path else None,
        )
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

        # Load body biomechanics for per-frame center of mass calculation, using
        # the tracker->canonical mapping that matches the configured detector
        # (RTMPose and MediaPipe use different keypoint naming conventions).
        # Validated once at init via skellyforge's AnatomicalStructure — no
        # Pydantic in the hot loop.
        detector_type = pipeline_config.camera_node_config.detector_type
        biomechanics = (
            load_body_biomechanics(detector_type)
            if aggregator_config.center_of_mass_enabled
            else None
        )

        # Create the skeleton rigidifier (canonical models + per-bone online
        # length estimators + forward-pass tree rigidifiers). Loaded once at
        # init; the per-frame hot path is pure numpy.
        skeleton_rigidifier: RealtimeSkeletonRigidifier | None = None
        rigidifier_filter_config: RealtimeFilterConfig | None = None
        if aggregator_config.skeleton_fitting_enabled:
            skeleton_rigidifier = RealtimeSkeletonRigidifier.create(
                detector_type=detector_type,
                height_mm=filter_config.height_mm,
                buffer_capacity=filter_config.segment_length_buffer_capacity,
                decay_tau_s=filter_config.segment_length_decay_s,
                fit_ratio=filter_config.segment_length_fit_ratio,
                min_samples=filter_config.segment_length_min_samples,
                agreement_tol=filter_config.segment_length_agreement_tol,
                max_reprojection_error=filter_config.segment_length_max_reprojection_error_px,
                countdown_s=filter_config.calibration_countdown_s,
                capture_min_visible_fraction=filter_config.calibration_capture_min_visible_fraction,
                capture_max_mean_error_px=filter_config.calibration_capture_max_mean_error_px,
                capture_consecutive_good_frames=filter_config.calibration_capture_consecutive_good_frames,
            )
            rigidifier_filter_config = filter_config
            logger.debug(
                f"RealtimeAggregationNode [{camera_group_id}] skeleton rigidifier created "
                f"(body bones: {len(skeleton_rigidifier.body_bone_lengths)}, "
                f"hand bones: {len(skeleton_rigidifier.right_hand_bone_lengths)})"
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
        # Wall-clock time we started waiting on the currently-expected frame's
        # skeleton result; None when not waiting. Reset whenever the wait
        # resolves (found, or times out and is abandoned).
        skeleton_wait_started_at: float | None = None
        latest_requested_frame: int = -1
        last_received_frame: int = -1
        last_calibration_poll: float = time.perf_counter()
        _empty_3d_logged: bool = False  # Rate-limit the "no 3D keypoints" warning
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
        # Centroidal kinematics (inertia ellipsoid + ground references) per frame.
        streaming_kinematics = StreamingKinematics()

        # Live body-proportion diagnostic: rolling-window limb-segment lengths,
        # checked periodically against human anthropometric proportions.
        body_proportion_monitor = (
            StreamingSegmentLengthMonitor()
            if aggregator_config.body_proportion_diagnostics_enabled
            else None
        )

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
                    # Honor a live change to the calibration source path.
                    _updated_calib_path = aggregator_config.calibration_toml_path
                    if calibration.set_source_path(
                        Path(_updated_calib_path) if _updated_calib_path else None
                    ):
                        logger.info(
                            f"RealtimeAggregationNode [{camera_group_id}] reloaded "
                            f"calibration from {calibration.calibration_path}"
                        )

                    # Rebuild biomechanics / skeleton rigidifier if the detector
                    # type changed (RTMPose <-> MediaPipe use different tracker
                    # keypoint names, so the loaded canonical mapping would
                    # otherwise silently go stale) or if center-of-mass /
                    # skeleton-fitting were toggled on/off.
                    new_detector_type = pipeline_config.camera_node_config.detector_type
                    detector_type_changed = new_detector_type != detector_type
                    detector_type = new_detector_type

                    if aggregator_config.center_of_mass_enabled:
                        if biomechanics is None or detector_type_changed:
                            biomechanics = load_body_biomechanics(detector_type)
                            logger.info(
                                f"RealtimeAggregationNode [{camera_group_id}] "
                                f"(re)loaded body biomechanics for detector_type={detector_type}"
                            )
                    else:
                        biomechanics = None

                    # Recreate the rigidifier when the detector naming changes or
                    # any fit parameter changed — silently stale fit params are
                    # worse than a one-time canonical-model reload.
                    filter_config_changed = (
                        rigidifier_filter_config is not None
                        and filter_config != rigidifier_filter_config
                    )
                    if aggregator_config.skeleton_fitting_enabled:
                        if (
                            skeleton_rigidifier is None
                            or detector_type_changed
                            or filter_config_changed
                        ):
                            skeleton_rigidifier = RealtimeSkeletonRigidifier.create(
                                detector_type=detector_type,
                                height_mm=filter_config.height_mm,
                                buffer_capacity=filter_config.segment_length_buffer_capacity,
                                decay_tau_s=filter_config.segment_length_decay_s,
                                fit_ratio=filter_config.segment_length_fit_ratio,
                                min_samples=filter_config.segment_length_min_samples,
                                agreement_tol=filter_config.segment_length_agreement_tol,
                                max_reprojection_error=filter_config.segment_length_max_reprojection_error_px,
                                countdown_s=filter_config.calibration_countdown_s,
                                capture_min_visible_fraction=filter_config.calibration_capture_min_visible_fraction,
                                capture_max_mean_error_px=filter_config.calibration_capture_max_mean_error_px,
                                capture_consecutive_good_frames=filter_config.calibration_capture_consecutive_good_frames,
                            )
                            rigidifier_filter_config = filter_config
                            logger.info(
                                f"RealtimeAggregationNode [{camera_group_id}] "
                                f"(re)created skeleton rigidifier for detector_type={detector_type}"
                            )
                    else:
                        skeleton_rigidifier = None
                        rigidifier_filter_config = None

                # ---- Handle skeleton fitter reset signals ----
                # Drain unconditionally so the queue can't grow while skeleton
                # fitting is disabled; reset once if anything was requested.
                reset_requested = False
                while True:
                    try:
                        skeleton_fitter_reset_sub.get_nowait()
                    except queue.Empty:
                        break
                    reset_requested = True
                if reset_requested and skeleton_rigidifier is not None:
                    skeleton_rigidifier.request_refit()
                    logger.info(
                        f"RealtimeAggregationNode [{camera_group_id}] segment-fit "
                        f"ritual armed (countdown → capture → freeze)"
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
                        streaming_kinematics.reset()
                        # New calibration → re-arm the refit ritual: the lengths
                        # were learned under the old calibration, so capture
                        # fresh ones under the new one.
                        if skeleton_rigidifier is not None:
                            skeleton_rigidifier.request_refit()

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
                if (pipeline_config.use_centralized_inference
                        and pipeline_config.camera_node_config.skeleton_tracking_enabled):
                    expected_frame = next(iter(camera_node_outputs.values())).frame_number
                    if expected_frame not in pending_skeleton_results:
                        now = time.perf_counter()
                        if skeleton_wait_started_at is None:
                            skeleton_wait_started_at = now
                            continue
                        elif now - skeleton_wait_started_at > _SKELETON_RESULT_WAIT_TIMEOUT_SECONDS:
                            # The result for this frame is never coming — most
                            # likely the SkeletonInferenceNode was restarted
                            # (e.g. detector swap) mid-flight and its pub/sub
                            # subscription was orphaned. Give up on this frame's
                            # skeleton rather than deadlocking the pipeline
                            # (which would also freeze the frontend camera feed,
                            # since it's served from this node's output).
                            logger.warning(
                                f"RealtimeAggregationNode [{camera_group_id}] gave up waiting "
                                f"on skeleton result for frame {expected_frame} after "
                                f"{_SKELETON_RESULT_WAIT_TIMEOUT_SECONDS}s — proceeding without it"
                            )
                            skeleton_wait_started_at = None
                        else:
                            # Camera outputs are ready but skeleton inference hasn't
                            # caught up yet. Loop again — `camera_node_outputs` stays
                            # populated, and the skeleton result will land in the
                            # `skeleton_inference_sub` drain at the top of the next
                            # iteration.
                            continue
                    else:
                        # Splice the per-camera skeletons into each CameraNodeOutputMessage
                        # so downstream triangulation code (which reads
                        # `output.skeleton_observation`) needs no changes.
                        skeleton_per_camera = pending_skeleton_results.pop(expected_frame)
                        for cam_id, output_msg in camera_node_outputs.items():
                            if output_msg is not None:
                                output_msg.skeleton_observation = skeleton_per_camera.get(cam_id)
                        skeleton_wait_started_at = None

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
                raw_errors_px: dict[str, float] = {}
                filtered_keypoints: dict[str, np.ndarray] = {}
                measured_keypoints: dict[str, np.ndarray] = {}
                skeleton_keypoints: dict[str, np.ndarray] = {}
                frame_time = time.perf_counter()
                com_result: CenterOfMassResult | None = None
                xcom: Point3d | None = None
                body_kinematics = None
                rigid_result: RigidifyResult | None = None
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
                        _merge_angulation(
                            angulation=calibration.try_angulate(
                                frame_number=last_received_frame,
                                frame_observations_by_camera=skeleton_observations_by_camera,
                                max_reprojection_error_px=filter_config.max_reprojection_error_px,
                                triangulation_config=aggregator_config.triangulation_config,
                            ),
                            into_points=raw_keypoints,
                            into_errors=raw_errors_px,
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
                        _merge_angulation(
                            angulation=calibration.try_angulate(
                                frame_number=last_received_frame,
                                frame_observations_by_camera=charuco_observations_by_camera,
                                max_reprojection_error_px=filter_config.max_reprojection_error_px,
                                triangulation_config=aggregator_config.triangulation_config,
                            ),
                            into_points=raw_keypoints,
                            into_errors=raw_errors_px,
                        )
                        if timer is not None:
                            timer.record("charuco_triangulation", (time.perf_counter() - t0) * 1e3)

                    if not raw_keypoints and skeleton_observations_by_camera and not _empty_3d_logged:
                        _empty_3d_logged = True
                        logger.warning(
                            f"RealtimeAggregationNode [{camera_group_id}]: "
                            f"skeleton observations received from {len(skeleton_observations_by_camera)} camera(s) "
                            f"but triangulation produced zero 3D keypoints. "
                            f"Check backend logs for 'no keypoints visible in ≥2 cameras' or reprojection error warnings. "
                            f"Calibration path: {calibration.calibration_path}"
                        )

                    # One Euro filter: smooth raw keypoints and gap-fill brief occlusions
                    if raw_keypoints:
                        t0 = time.perf_counter() if timer is not None else 0.0
                        filter_result = keypoint_filter.filter(
                            t=frame_time,
                            raw_keypoints=raw_keypoints,
                        )
                        filtered_keypoints = filter_result.positions
                        # Real measurements only: gap-filled (extrapolated)
                        # points still display, but never teach bone lengths.
                        measured_keypoints = {
                            name: pos
                            for name, pos in filter_result.positions.items()
                            if name not in filter_result.predicted_names
                        }
                        if timer is not None:
                            timer.record("keypoint_filter", (time.perf_counter() - t0) * 1e3)

                    # Velocity gate: reject teleportation spikes
                    if aggregator_config.filter_enabled:
                        if raw_keypoints:
                            t0 = time.perf_counter() if timer is not None else 0.0
                            gate_result: GateResult = point_gate.gate(
                                t=frame_time,
                                points=raw_keypoints,
                            )
                            for point_name, coords in gate_result.positions.items():
                                if not np.any(np.isnan(coords)):
                                    filtered_keypoints[point_name] = coords
                            if timer is not None:
                                timer.record("velocity_gate", (time.perf_counter() - t0) * 1e3)

                    # ---- Rigid-body skeleton correction ----
                    if (
                        skeleton_rigidifier is not None
                        and filtered_keypoints
                    ):
                        t0 = time.perf_counter() if timer is not None else 0.0
                        rigid_result = skeleton_rigidifier.rigidify_frame(
                            filtered_keypoints,
                            measured=measured_keypoints,
                            t=frame_time,
                            errors=raw_errors_px if raw_errors_px else None,
                        )
                        skeleton_fit_state_pub.put(
                            SkeletonFitStateMessage.from_snapshot(
                                skeleton_rigidifier.fit_state
                            )
                        )
                        if timer is not None:
                            timer.record("skeleton_fitting", (time.perf_counter() - t0) * 1e3)

                    # ---- Center of mass ----
                    # Prefer the rigidified skeleton (matches posthoc, which
                    # computes CoM on rigid_xyz); fall back to raw keypoints when
                    # the rigidifier is disabled.
                    if (
                        biomechanics is not None
                        and aggregator_config.center_of_mass_enabled
                        and (
                            (rigid_result is not None and rigid_result.body_positions)
                            or filtered_keypoints
                        )
                    ):
                        t0 = time.perf_counter() if timer is not None else 0.0
                        if rigid_result is not None and rigid_result.body_positions:
                            com_result = calculate_center_of_mass_from_canonical(
                                rigid_result.body_positions,
                                biomechanics,
                            )
                        else:
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
                        #
                        # # ---- Centroidal kinematics (inertia ellipsoid + ground refs) ----
                        # if not np.any(np.isnan(com_result.total_body_com)):
                        #     body_kinematics = streaming_kinematics.update(
                        #         t=now_com,
                        #         whole_body_com=com_result.total_body_com,
                        #         segment_coms=com_result.segment_coms,
                        #         segment_masses=biomechanics.mass_percentages,
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

                # ---- Live body-proportion diagnostic (rolling window) ----
                # Measures limb-segment lengths from the raw triangulated keypoints
                # and flags when the realtime reconstruction drifts from human
                # anthropometric proportions. Per-frame cost is ~8 distances.
                if body_proportion_monitor is not None:
                    body_proportion_monitor.update(filtered_keypoints)
                    if body_proportion_monitor.n_seen % DEFAULT_DIAGNOSTIC_INTERVAL == 0:
                        proportion_report = body_proportion_monitor.report()
                        if (
                            len(proportion_report.assessable())
                            >= proportion_report.thresholds.min_assessable_segments
                        ):
                            drift = proportion_report.human_shape_violations(check_rigidity=False)
                            # if drift:
                            #     logger.warning(
                            #         f"RealtimeAggregationNode [{camera_group_id}] "
                            #         f"body-proportion drift: " + "; ".join(drift)
                            #     )
                            # else:
                            #     logger.debug(
                            #         f"RealtimeAggregationNode [{camera_group_id}] body "
                            #         f"proportions OK — implied height "
                            #         f"{proportion_report.implied_height_median_mm:.0f}mm "
                            #         f"(cv {proportion_report.implied_height_cv:.2f})"
                            #     )

                # ---- Publish aggregated output ----
                aggregation_output_pub.put(
                    AggregationNodeOutputMessage(
                        frame_number=last_received_frame,
                        pipeline_id=ipc.pipeline_id,
                        pipeline_config=pipeline_config,
                        camera_group_id=camera_group_id,
                        camera_node_outputs=frame_n_outputs,
                        keypoints_arrays=filtered_keypoints,
                        center_of_mass_result=com_result,
                        xcom=xcom,
                        skeleton=(
                            {
                                **rigid_result.body_positions,
                                **rigid_result.left_hand_positions,
                                **rigid_result.right_hand_positions,
                            }
                            if rigid_result is not None
                            else None
                        ),
                        body_kinematics=body_kinematics,
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
