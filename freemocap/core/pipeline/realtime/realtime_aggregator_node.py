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

Reconstruction runs ONCE PER TRACKED SKELETON on the filtered 3D keypoints — a session
tracking a person and a charuco board runs it twice. Each skeleton's bundle carries the
mapping that feeds it, the fitter that sizes it and the roll convention it opted into, and
``reconstruct_skeleton`` does the per-skeleton work; this node owns the shared parts
(triangulation, smoothing, gating) and the cross-frame state a pure function cannot hold.
The reset signal clears every skeleton's fit windows so the next ~window frames re-fit.
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
from skellyforge.core.biomechanics.ground_reference import (
    GRAVITY_ACCELERATION,
    extrapolated_center_of_mass,
)
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import (
    CameraGroupSharedMemory,
    CameraGroupSharedMemoryDTO,
)
from skellycam.core.types.type_overloads import (
    CameraGroupIdString,
    CameraIdString,
    TopicSubscriptionQueue,
)
from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition
from freemocap.core.skeletons.reconstruct_skeleton import reconstruct_skeleton
from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction
from skellyforge.core.skeleton.pose.model_scale_fitting import (
    scale_voting_segment_names,
)

from freemocap.core.skeletons.reconstruction_state import (
    SkeletonReconstructionState,
    streaming_model_scale_source,
)
from freemocap.core.skeletons.tracked_skeleton_set import (
    TrackedSkeletonSet,
    build_tracked_skeleton_set,
)
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.core.streaming.channel_helpers import (
    origin_landmark_names,
)

from freemocap.core.pipeline.abcs.aggregator_node_abc import AggregatorNode
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.realtime.realtime_pipeline_config import (
    RealtimePipelineConfig,
)
from freemocap.core.pipeline.pipeline_stage_timer import PipelineStageTimer
from freemocap.core.pipeline.pipeline_timing_reporter import PipelineTimingReporter
from freemocap.core.tasks.calibration.shared.calibration_camera_binding import (
    CalibrationMatchKind,
)
from freemocap.core.tasks.calibration.shared.calibration_state import (
    CalibrationStateTracker,
)
from freemocap.core.tasks.triangulation.helpers.angulation_result import (
    AngulationResult,
)
from freemocap.core.tasks.mocap.realtime_filtering.realtime_point_gate import (
    RealtimePointGate,
    GateResult,
)
from freemocap.core.tasks.mocap.realtime_filtering.realtime_filter_config import (
    RealtimeFilterConfig,
)
from freemocap.core.pipeline.realtime.realtime_keypoint_filter import (
    RealtimeKeypointFilter,
)
from freemocap.core.types.type_overloads import (
    TopicPublicationQueue,
    TrackedPointNameString,
)
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import (
    CameraNodeOutputMessage,
    CameraNodeOutputTopic,
    PipelineConfigUpdateTopic,
    ProcessFrameNumberTopic,
    ProcessFrameNumberMessage,
    AggregationNodeOutputMessage,
    LiveCameraCalibrationBinding,
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

# Max time to wait for a specific frame's skeleton-inference result before
# giving up on it and proceeding without a skeleton for that frame. Without
# this, a SkeletonInferenceNode restart (e.g. detector swap) orphans whatever
# frame request the old node's process was mid-flight on — its pub/sub
# subscription dies with it and the new node's subscription only sees
# requests published after it was created — so waiting unconditionally here
# would deadlock the whole pipeline (camera feed included) forever.
_SKELETON_RESULT_WAIT_TIMEOUT_SECONDS: float = 2.0
_SKELETON_RESULT_POLL_SECONDS: float = 0.005
"""Bounded wait on the skeleton-result queue while a frame's inference lands.

Small enough to keep frame pickup responsive, big enough that waiting costs
~nothing instead of burning the loop's core at 100%."""

logger = logging.getLogger(__name__)

# How often (seconds) to poll the calibration file for changes
CALIBRATION_POLL_INTERVAL_SECONDS: float = 1.0


def _to_blender(position: np.ndarray) -> np.ndarray:
    """FreeMoCap (+X forward, +Y left, +Z up) -> Blender (+X right, +Y forward, +Z up).

    Both frames are right-handed and +Z up, so this is a 90-degree rotation about Z.
    """
    return np.array([-position[1], position[0], position[2]], dtype=np.float64)


def _from_blender(position: np.ndarray) -> np.ndarray:
    """Blender (+X right, +Y forward) -> FreeMoCap (+X forward, +Y left), the inverse."""
    return np.array([position[1], -position[0], position[2]], dtype=np.float64)


def _reproject_segment_origins(
    *,
    calibration,
    skeleton: SkeletonDefinition,
    solver_landmarks: dict[str, np.ndarray],
) -> dict[CameraIdString, dict[TrackedPointNameString, tuple[float, float]]]:
    """Project one skeleton's segment origins into every camera.

    Builds an (n_segments, 3) array of origin positions in that skeleton's own names, runs
    it through the calibration's triangulator projection, and returns
    ``{camera_id: {segment_name: (x, y)}}`` in capture-resolution px. Origins not hydrated
    this frame project to NaN and are dropped.
    """
    origin_names = origin_landmark_names(skeleton)
    segment_names = list(skeleton.segments)
    origins = np.full((len(segment_names), 3), np.nan, dtype=np.float64)
    for i, name in enumerate(segment_names):
        pos = solver_landmarks.get(origin_names[name])
        if pos is not None and not np.any(np.isnan(pos)):
            origins[i] = _from_blender(np.asarray(pos, dtype=np.float64)[:3])
    projected = calibration.triangulator.project(origins)  # (n_cameras, 60, 2)
    # The triangulator is keyed by CALIBRATION camera id; every consumer of these
    # overlays looks them up by LIVE camera id. Translate here, or the overlays
    # silently vanish for any rig whose ids drifted from the calibration.
    binding = calibration.binding
    live_id_by_calibration_id = (
        binding.live_id_for_calibration_id if binding is not None else {}
    )
    out: dict[CameraIdString, dict[TrackedPointNameString, tuple[float, float]]] = {}
    for cam_idx, calibration_camera_id in enumerate(
        calibration.triangulator.camera_ids
    ):
        live_camera_id = live_id_by_calibration_id.get(calibration_camera_id)
        if live_camera_id is None:
            continue
        per_cam: dict[TrackedPointNameString, tuple[float, float]] = {}
        for i, name in enumerate(segment_names):
            x, y = projected[cam_idx, i]
            if not (np.isnan(x) or np.isnan(y)):
                per_cam[name] = (float(x), float(y))
        out[live_camera_id] = per_cam
    return out


def _publishable_calibration_bindings(
    *,
    calibration,
    live_camera_indices: dict[CameraIdString, int],
) -> tuple[LiveCameraCalibrationBinding, ...]:
    """Flatten the calibration binding into the per-camera form that goes on the wire.

    Emits an entry for EVERY live camera, matched or not. The websocket layer describes
    the whole live camera set from this; dropping unmatched cameras here is what used to
    leave the frontend with no way to know a camera had no usable calibration.
    """
    binding = calibration.binding
    return tuple(
        LiveCameraCalibrationBinding(
            live_camera_id=live_camera_id,
            camera_index=camera_index,
            match_kind=(
                binding.kind.value
                if binding is not None
                and binding.by_live_id.get(live_camera_id) is not None
                else CalibrationMatchKind.UNMATCHED.value
            ),
            calibration_camera_id=(
                model.id
                if binding is not None
                and (model := binding.by_live_id.get(live_camera_id))
                else None
            ),
            camera_model=(
                binding.by_live_id.get(live_camera_id) if binding is not None else None
            ),
        )
        for live_camera_id, camera_index in live_camera_indices.items()
    )


def _fill_extrapolated_center_of_mass(
    *,
    reconstruction: SkeletonReconstruction,
    state: SkeletonReconstructionState,
    enabled: bool,
) -> None:
    """Add this skeleton's XCoM, from the change in its centre of mass since last frame.

    Cross-frame state, which is why it lives on the skeleton's own reconstruction state
    rather than in the pure per-frame reconstruction. Per-skeleton so two tracked skeletons
    cannot borrow each other's velocity.

    This is the STREAMING estimate: a causal two-point backward difference, because a live
    frame cannot see t+1. A batch driver takes velocity from the whole trajectory via
    `center_of_mass_velocity` and feeds the SAME `extrapolated_center_of_mass` below. That
    difference is temporal policy, not a second implementation — do not "unify" them.

    Skipped entirely for a skeleton that did not opt into `extrapolated_center_of_mass`:
    XCoM is a balance quantity about a body standing on the ground, and it means nothing
    for a calibration board held in the air.
    """
    center_of_mass = reconstruction.center_of_mass
    if not enabled or center_of_mass is None:
        return
    now = time.perf_counter()
    previous = state.previous_center_of_mass
    if previous is not None and float(center_of_mass[2]) > 0.0:
        previous_center, previous_time = previous
        elapsed = now - previous_time
        if elapsed > 0:
            reconstruction.extrapolated_center_of_mass = extrapolated_center_of_mass(
                com=center_of_mass,
                com_velocity=(center_of_mass - previous_center) / elapsed,
                gravity=GRAVITY_ACCELERATION,
            )
    state.previous_center_of_mass = (center_of_mass.copy(), now)


def _log_reconstruction_observability(
    *,
    bundles: tuple[TrackedSkeletonBundle, ...],
    reconstructions: dict[str, SkeletonReconstruction],
    already_logged: set[str],
) -> None:
    """Say once per run when a skeleton is not reconstructing, and how badly.

    Once per run rather than per frame, and keyed by model so one skeleton going quiet
    cannot mask another's.
    """
    for bundle in bundles:
        reconstruction = reconstructions.get(bundle.model_id)
        expected = len(bundle.skeleton.segments)
        if reconstruction is None or not reconstruction.segment_rotations_world:
            key = f"{bundle.model_id}:no_orientations"
            if key not in already_logged:
                already_logged.add(key)
            continue
        solved = len(reconstruction.segment_rotations_world)
        if solved < expected:
            key = f"{bundle.model_id}:partial_orientations"
            if key not in already_logged:
                already_logged.add(key)
                missing = sorted(
                    set(bundle.skeleton.segments)
                    - set(reconstruction.segment_rotations_world)
                )
                logger.warning(
                    f"Skeleton {bundle.model_id!r} produced {solved}/{expected} "
                    f"orientations — unsolved segments: {missing}"
                )
        if reconstruction.fitted_scale_mm is None:
            key = f"{bundle.model_id}:no_scale"
            if key not in already_logged:
                already_logged.add(key)
                logger.info(
                    f"Skeleton {bundle.model_id!r} has no measured size yet, so its "
                    "segment lengths and fitted scale stay off the wire until a segment "
                    "that may set the scale is seen. Voting segments: "
                    f"{len(scale_voting_segment_names(skeleton=bundle.skeleton, measured_landmark_names=bundle.landmark_mapping.directly_measured_landmark_names))}"
                )


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
                )
                if config.log_pipeline_times
                else None,
                result_ready_event=result_ready_event,
                result_consumed_event=result_consumed_event,
                skeleton_fitter_reset_sub=skeleton_fitter_reset_sub,
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
    ) -> None:
        logger.debug(f"RealtimeAggregationNode [{camera_group_id}] initializing")
        aggregator_config = pipeline_config.aggregator_config
        camera_group_shm = CameraGroupSharedMemory.recreate(
            shm_dto=camera_group_shm_dto,
            read_only=True,
        )
        _configured_calib_path = aggregator_config.calibration_toml_path
        calibration = CalibrationStateTracker.create_and_try_load(
            calibration_toml_path=Path(_configured_calib_path)
            if _configured_calib_path
            else None,
        )
        # The live camera set this pipeline owns, with the structured index each
        # camera reports. Fixed for the pipeline's life, so binding is settled here.
        live_camera_indices = {
            cam_id: config.camera_index
            for cam_id, config in camera_group_shm.camera_configs.items()
            if cam_id in camera_ids
        }
        if calibration.is_valid:
            logger.info(
                f"RealtimeAggregationNode [{camera_group_id}] loaded calibration "
                f"from {calibration.calibration_path}"
            )
            calibration.bind_live_cameras(live_camera_indices=live_camera_indices)
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

        detector_type = pipeline_config.camera_node_config.detector_type
        # Every skeleton this run tracks, each bundled with what reconstructs it. Built
        # once per run — every recording gets fresh fit windows, no module globals — and
        # rebuilt when the detector changes, because which landmarks are MEASURED (as
        # opposed to constructed from authored ratios) is a property of its mapping.
        skeleton_set: TrackedSkeletonSet = build_tracked_skeleton_set(
            camera_node_config=pipeline_config.camera_node_config,
            scale_source_for=streaming_model_scale_source(
                window_frames=filter_config.segment_scale_window_frames
            ),
        )

        skeleton_fitting_enabled: bool = aggregator_config.skeleton_fitting_enabled

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

        log_pipeline_times = pipeline_config.log_pipeline_times
        timer = (
            PipelineStageTimer(name=f"AggregatorNode-{camera_group_id}")
            if log_pipeline_times
            else None
        )
        t_frame_requested: float = time.perf_counter() if timer is not None else 0.0
        # Skip the first frame_collection_wait / loop_time samples — those
        # measure aggregator-startup → first-frame-arrival, which is dominated
        # by camera warmup (~5-7s) and is not a steady-state metric.
        recorded_first_frame: bool = False
        # Observability: log each failure class ONCE per run per skeleton, not per frame.
        skeleton_observability_logged: set[str] = set()

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
            logger.debug(
                f"RealtimeAggregationNode [{camera_group_id}] entering main loop"
            )
            while ipc.should_continue and not shutdown_self_flag.value:
                # ---- Handle config updates ----
                while True:
                    try:
                        msg: PipelineConfigUpdateMessage = (
                            pipeline_config_sub.get_nowait()
                        )
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
                    # keypoint names, so the loaded standard-human mapping would
                    # otherwise silently go stale) or if center-of-mass /
                    # skeleton-fitting were toggled on/off.
                    new_detector_type = pipeline_config.camera_node_config.detector_type
                    detector_type_changed = new_detector_type != detector_type
                    detector_type = new_detector_type

                    if detector_type_changed:
                        # A different detector measures different landmarks, so which
                        # segments may set a skeleton's scale changes with it. Rebuilding
                        # also drops the old detector's readings, which is right: they
                        # were measured through a different naming convention.
                        # Bundles AND their states together: the old detector's scale
                        # readings and roll carry must not survive into the new mapping.
                        skeleton_set = build_tracked_skeleton_set(
                            camera_node_config=pipeline_config.camera_node_config,
                            scale_source_for=streaming_model_scale_source(
                                window_frames=filter_config.segment_scale_window_frames
                            ),
                        )
                        logger.info(
                            f"RealtimeAggregationNode [{camera_group_id}] "
                            f"(re)loaded body biomechanics for detector_type={detector_type}"
                        )

                    # Skeleton fitting is stateless — nothing to recreate.
                    skeleton_fitting_enabled = (
                        aggregator_config.skeleton_fitting_enabled
                    )

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
                if reset_requested:
                    logger.info(
                        f"RealtimeAggregationNode [{camera_group_id}] skeleton fit reset"
                    )
                    skeleton_set.reset()
                    skeleton_observability_logged.clear()

                # ---- Periodically check if calibration file changed on disk ----
                now = time.perf_counter()
                if now - last_calibration_poll >= CALIBRATION_POLL_INTERVAL_SECONDS:
                    last_calibration_poll = now
                    if calibration.check_for_update():
                        logger.info(
                            f"RealtimeAggregationNode [{camera_group_id}] "
                            f"hot-reloaded calibration from {calibration.calibration_path}"
                        )
                        calibration.bind_live_cameras(
                            live_camera_indices=live_camera_indices
                        )
                        # Coordinate frame may have changed — reset filter + gate + XCoM
                        # tracking, and the body scale with them: every reading in the
                        # fitter's windows was measured in the old frame's units.
                        keypoint_filter.reset()
                        point_gate.reset()
                        skeleton_set.reset()
                        skeleton_observability_logged.clear()

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
                if (
                    current_multiframe_number > latest_requested_frame
                    and last_received_frame >= latest_requested_frame
                    and result_consumed_event.is_set()
                ):
                    process_frame_number_pub.put(
                        ProcessFrameNumberMessage(
                            frame_number=current_multiframe_number,
                        ),
                    )
                    latest_requested_frame = current_multiframe_number
                    t_frame_requested = (
                        time.perf_counter() if timer is not None else 0.0
                    )

                # ---- Collect skeleton inference results (GPU mode) ----
                # Drained on every iteration so they're available whenever the
                # corresponding camera-node charuco outputs finish arriving.
                while True:
                    try:
                        skel_msg: SkeletonInferenceResultMessage = (
                            skeleton_inference_sub.get_nowait()
                        )
                    except queue.Empty:
                        break
                    pending_skeleton_results[skel_msg.frame_number] = (
                        skel_msg.per_camera_skeleton
                    )
                # Bound the pending dict so a lagging camera can't grow it forever.
                if len(pending_skeleton_results) > _MAX_PENDING_SKELETON_RESULTS:
                    oldest = sorted(pending_skeleton_results.keys())[
                        : len(pending_skeleton_results) - _MAX_PENDING_SKELETON_RESULTS
                    ]
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
                        cam_output: CameraNodeOutputMessage = camera_node_sub.get(
                            timeout=0.005
                        )
                    except queue.Empty:
                        continue
                    except InterruptedError:
                        # Windows Ctrl+C interrupts the wait syscall during
                        # shutdown; re-check the loop condition.
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
                if (
                    pipeline_config.use_centralized_inference
                    and pipeline_config.camera_node_config.skeleton_tracking_enabled
                ):
                    expected_frame = next(
                        iter(camera_node_outputs.values())
                    ).frame_number
                    if expected_frame not in pending_skeleton_results:
                        now = time.perf_counter()
                        if skeleton_wait_started_at is None:
                            skeleton_wait_started_at = now
                            continue
                        elif (
                            now - skeleton_wait_started_at
                            > _SKELETON_RESULT_WAIT_TIMEOUT_SECONDS
                        ):
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
                            # Camera outputs are ready but skeleton inference
                            # hasn't caught up yet — WAIT on the result queue
                            # (bounded) instead of spinning hot through the
                            # whole loop body. This branch is steady state
                            # whenever the batched GPU call finishes after the
                            # camera nodes, which is the common case in the
                            # default configuration. The overall wait budget
                            # is still enforced above against
                            # `skeleton_wait_started_at`.
                            try:
                                skel_msg: SkeletonInferenceResultMessage = (
                                    skeleton_inference_sub.get(
                                        timeout=_SKELETON_RESULT_POLL_SECONDS,
                                    )
                                )
                                pending_skeleton_results[skel_msg.frame_number] = (
                                    skel_msg.per_camera_skeleton
                                )
                            except (queue.Empty, InterruptedError):
                                pass
                            continue
                    else:
                        # Splice the per-camera skeletons into each CameraNodeOutputMessage
                        # so downstream triangulation code (which reads
                        # `output.skeleton_observation`) needs no changes.
                        skeleton_per_camera = pending_skeleton_results.pop(
                            expected_frame
                        )
                        for cam_id, output_msg in camera_node_outputs.items():
                            if output_msg is not None:
                                output_msg.skeleton_observation = (
                                    skeleton_per_camera.get(cam_id)
                                )
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
                    timer.record(
                        "frame_collection_wait",
                        (t_frame_start - t_frame_requested) * 1e3,
                    )

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
                    t_frame_requested = (
                        time.perf_counter() if timer is not None else 0.0
                    )
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
                # One reconstruction per tracked skeleton, filled below. A skeleton that
                # did not hydrate this frame is simply absent.
                reconstructions: dict[str, SkeletonReconstruction] = {}
                if (
                    calibration.is_applicable() or len(camera_ids) == 1
                ) and aggregator_config.triangulation_enabled:
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
                            timer.record(
                                "skeleton_triangulation",
                                (time.perf_counter() - t0) * 1e3,
                            )

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
                            timer.record(
                                "charuco_triangulation",
                                (time.perf_counter() - t0) * 1e3,
                            )

                    # Convert the triangulated keypoints to Blender once at the source:
                    # the skeleton solve and the wire are Blender-native (+X right, +Y forward, +Z up).
                    raw_keypoints = {
                        name: _to_blender(pos) for name, pos in raw_keypoints.items()
                    }

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
                            timer.record(
                                "keypoint_filter", (time.perf_counter() - t0) * 1e3
                            )

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
                                timer.record(
                                    "velocity_gate", (time.perf_counter() - t0) * 1e3
                                )

                    # ---- Reconstruct each tracked skeleton ----
                    # One pass per skeleton: map -> hydrate -> resolve roll -> fit scale ->
                    # size every segment -> place the centre of mass. A session tracking a
                    # person and a charuco board runs this twice, and nothing below knows
                    # which is which.
                    if skeleton_fitting_enabled and filtered_keypoints:
                        t0 = time.perf_counter() if timer is not None else 0.0
                        for bundle in skeleton_set.bundles:
                            state = skeleton_set.state_for(bundle)
                            reconstruction = reconstruct_skeleton(
                                bundle=bundle,
                                state=state,
                                filtered_keypoints=filtered_keypoints,
                                compute_center_of_mass=aggregator_config.center_of_mass_enabled,
                            )
                            if reconstruction is None:
                                continue
                            _fill_extrapolated_center_of_mass(
                                reconstruction=reconstruction,
                                state=state,
                                enabled="extrapolated_center_of_mass"
                                in bundle.skeleton.derived_quantities,
                            )
                            if calibration.is_applicable():
                                reconstruction.reprojected_segment_origins = (
                                    _reproject_segment_origins(
                                        calibration=calibration,
                                        skeleton=bundle.skeleton,
                                        solver_landmarks=reconstruction.landmarks,
                                    )
                                )
                            reconstructions[bundle.model_id] = reconstruction
                        if timer is not None:
                            timer.record(
                                "skeleton_fitting", (time.perf_counter() - t0) * 1e3
                            )

                        _log_reconstruction_observability(
                            bundles=skeleton_set.bundles,
                            reconstructions=reconstructions,
                            already_logged=skeleton_observability_logged,
                        )

                # Convert to Point3d once at the end for the output message
                if timer is not None:
                    timer.record(
                        "full_frame_processing",
                        (time.perf_counter() - t_frame_start) * 1e3,
                    )
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
                # Every tracked skeleton's reconstruction, keyed by model. Each carries
                # its own fitted lengths (covering EVERY segment — the ones nothing saw
                # are sized by its fitted scale), rotations, joint angles and CoM.
                aggregation_output_pub.put(
                    AggregationNodeOutputMessage(
                        frame_number=last_received_frame,
                        pipeline_id=ipc.pipeline_id,
                        pipeline_config=pipeline_config,
                        camera_group_id=camera_group_id,
                        camera_node_outputs=frame_n_outputs,
                        keypoints_arrays=filtered_keypoints,
                        reconstructions=reconstructions,
                        calibration_bindings=_publishable_calibration_bindings(
                            calibration=calibration,
                            live_camera_indices=live_camera_indices,
                        ),
                        calibration_applicable=calibration.is_applicable(),
                    ),
                )
                # Mark the slot as full and not-yet-consumed; the consumer
                # (websocket relay via RealtimePipeline.get_latest_aggregator_output)
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
