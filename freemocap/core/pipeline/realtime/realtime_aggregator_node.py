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

Skeleton fitting runs on the filtered 3D keypoints: the tracker mapping names them
as standard-human landmarks, ``hydrate_skeleton`` recovers each segment's pose
closed-form, and ``ContinuousRollResolver`` supplies the roll two landmarks leave
free. The standard human is authored as fractions of body height, so hydration
also recovers each segment's SIZE, and ``StreamingBodyScaleFitter`` pools those
readings into the subject's height plus a per-segment scale — which is what sizes
the segments the cameras cannot see. The reset signal clears those windows so the
next ~window frames re-fit from scratch.
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
from freemocap.core.tasks.mocap.tracker_mappings import load_standard_human_mapping
from skellyforge.core.biomechanics.anthropometric_parameters import AnthropometricParameters
from skellyforge.core.biomechanics.center_of_mass import (
    CenterOfMassDefinitions,
    compute_segment_coms,
    landmark_world_positions,
)
from skellyforge.core.biomechanics.composite_inertia import whole_body_center_of_mass
from skellyforge.core.biomechanics.ground_reference import (
    GRAVITY_ACCELERATION,
    extrapolated_center_of_mass,
)
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import (
    CameraGroupSharedMemory,
    CameraGroupSharedMemoryDTO,
)
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, TopicSubscriptionQueue
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellyforge.core.skeleton.pose.body_scale_fitting import (
    BodyScaleFit,
    StreamingBodyScaleFitter,
    body_scale_voting_segment_names,
)
from skellyforge.core.skeleton.pose.hydration import hydrate_skeleton
from skellyforge.core.skeleton.pose.roll_resolution import ContinuousRollResolver
from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition
from freemocap.core.streaming.channel_helpers import (
    origin_landmark_names,
)
from skellyforge.core.skeleton.pose.rest_pose import RestPose

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
from freemocap.core.types.type_overloads import TopicPublicationQueue, TrackedPointNameString
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
        standard_human: SkeletonDefinition,
        solver_landmarks: dict[str, np.ndarray],
) -> dict[CameraIdString, dict[TrackedPointNameString, tuple[float, float]]]:
    """Project the fitted skeleton's segment origins into every camera.

    Builds one (60, 3) array of origin positions in the solver's standard-human
    names, runs it through the calibration's triangulator projection, and
    returns ``{camera_id: {segment_name: (x, y)}}`` in capture-resolution px.
    Origins not hydrated this frame project to NaN and are dropped.
    """
    origin_names = origin_landmark_names(standard_human)
    segment_names = list(standard_human.segments)
    origins = np.full((len(segment_names), 3), np.nan, dtype=np.float64)
    for i, name in enumerate(segment_names):
        pos = solver_landmarks.get(origin_names[name])
        if pos is not None and not np.any(np.isnan(pos)):
            origins[i] = _from_blender(np.asarray(pos, dtype=np.float64)[:3])
    projected = calibration.triangulator.project(origins)  # (n_cameras, 60, 2)
    out: dict[CameraIdString, dict[TrackedPointNameString, tuple[float, float]]] = {}
    for cam_idx, camera_id in enumerate(calibration.triangulator.camera_ids):
        per_cam: dict[TrackedPointNameString, tuple[float, float]] = {}
        for i, name in enumerate(segment_names):
            x, y = projected[cam_idx, i]
            if not (np.isnan(x) or np.isnan(y)):
                per_cam[name] = (float(x), float(y))
        out[camera_id] = per_cam
    return out


def _build_body_scale_fitter(
        *,
        standard_human: SkeletonDefinition,
        standard_human_mapping,
        window_frames: int,
) -> StreamingBodyScaleFitter:
    """A body-scale fitter that only lets genuinely measured segments set the height.

    The tracker mapping constructs a good many standard-human landmarks from authored
    ratios of a measured span — the sternoclavicular joints, the xiphoid process. Those
    are fine POSITIONS but they are not independent evidence about how big the subject is,
    and because they are nearly noise-free a consistency-weighted estimator would rank
    them as its best evidence. The mapping says which of its outputs it measures; the
    skeleton says which segments those make measurable.
    """
    return StreamingBodyScaleFitter(
        skeleton=standard_human,
        voting_segment_names=body_scale_voting_segment_names(
            skeleton=standard_human,
            measured_landmark_names=standard_human_mapping.directly_measured_landmark_names,
        ),
        window_frames=window_frames,
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
                ) if config.log_pipeline_times else None,
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
        # the tracker→standard-human mapping that matches the configured detector
        # (RTMPose and MediaPipe use different keypoint naming conventions).
        # No Pydantic in the hot loop — the mapping is a plain dict applied per frame.
        detector_type = pipeline_config.camera_node_config.detector_type
        # The body biomechanics carries the tracker->standard-human mapping —
        # needed by the rigidifier + solver regardless of center-of-mass.
        standard_human_mapping = load_standard_human_mapping(detector_type)

        # Composed standard human — shared by the skeleton rigidifier (segment
        # trees) and the orientation solver (reference geometry). Built once per
        # run (D16): the model is cheap to build, and every recording gets a
        # fresh instance — no module globals.
        standard_human = SkeletonDefinition.from_default_yaml()

        # Skeleton fitting is stateless: rigidify_landmarks runs per frame from
        # the loaded model + T-pose. Nothing is created or recreated.
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
        timer = PipelineStageTimer(name=f"AggregatorNode-{camera_group_id}") if log_pipeline_times else None
        t_frame_requested: float = time.perf_counter() if timer is not None else 0.0
        # Skip the first frame_collection_wait / loop_time samples — those
        # measure aggregator-startup → first-frame-arrival, which is dominated
        # by camera warmup (~5-7s) and is not a steady-state metric.
        recorded_first_frame: bool = False
        # XCoM velocity tracking: previous CoM position + timestamp for dt.
        prev_com: np.ndarray | None = None
        prev_com_time: float | None = None
        # Per-segment orientation history: carries the critically damped twist
        # state and the timestamp the next frame's dt is measured against. Scoped
        # to this run — at module scope, concurrent pipelines would share
        # smoothing state and damping would persist across recordings.
        anthropometric = AnthropometricParameters.from_default_yaml()
        com_definitions = CenterOfMassDefinitions.from_default_yaml()
        com_definitions.validate_against(skeleton=standard_human)
        segment_masses: dict[str, float] = {}
        for definition in com_definitions.definitions.values():
            mass = anthropometric.get(name=definition.name).mass_fraction * 70.0
            for full_name, _side in definition.side_entries:
                segment_masses[full_name] = mass
        # Observability: log each skeleton-failure class ONCE per run, not per frame.
        skeleton_observability_logged: set[str] = set()
        # The standard human is authored as fractions of body height, so it has no size
        # until it is fitted. This holds a rolling window of every visible segment's
        # reading of how big the subject is, and turns them into one height plus a
        # per-segment scale — which is what sizes the segments nothing can see.
        # Rebuilt whenever the detector changes, because which landmarks are MEASURED
        # (as opposed to constructed from authored ratios) is a property of the mapping,
        # and only measured ones are allowed to set the height.
        body_scale_fitter = _build_body_scale_fitter(
            standard_human=standard_human,
            standard_human_mapping=standard_human_mapping,
            window_frames=filter_config.segment_scale_window_frames,
        )
        # The rest pose supplies the roll resolver's seed and the parent tree the local
        # rotations are composed against. Its geometry is proportional; sizing it is the
        # fit's job, not this map's.
        rest_pose = RestPose.from_default_yaml(skeleton=standard_human)
        roll_resolver = ContinuousRollResolver.for_skeleton(
            skeleton=standard_human,
            rest_relative_orientations=rest_pose.relative_orientations,
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
                    # keypoint names, so the loaded standard-human mapping would
                    # otherwise silently go stale) or if center-of-mass /
                    # skeleton-fitting were toggled on/off.
                    new_detector_type = pipeline_config.camera_node_config.detector_type
                    detector_type_changed = new_detector_type != detector_type
                    detector_type = new_detector_type

                    if standard_human_mapping is None or detector_type_changed:
                        standard_human_mapping = load_standard_human_mapping(detector_type)
                        # A different detector measures different landmarks, so which
                        # segments may set the body height changes with it. Rebuilding
                        # also drops the old detector's readings, which is right: they
                        # were measured through a different naming convention.
                        body_scale_fitter = _build_body_scale_fitter(
                            standard_human=standard_human,
                            standard_human_mapping=standard_human_mapping,
                            window_frames=filter_config.segment_scale_window_frames,
                        )
                        logger.info(
                            f"RealtimeAggregationNode [{camera_group_id}] "
                            f"(re)loaded body biomechanics for detector_type={detector_type}"
                        )

                    # Skeleton fitting is stateless — nothing to recreate.
                    skeleton_fitting_enabled = aggregator_config.skeleton_fitting_enabled

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
                    roll_resolver.reset()
                    body_scale_fitter.reset()
                    skeleton_observability_logged.discard("no_body_scale")

                # ---- Periodically check if calibration file changed on disk ----
                now = time.perf_counter()
                if now - last_calibration_poll >= CALIBRATION_POLL_INTERVAL_SECONDS:
                    last_calibration_poll = now
                    if calibration.check_for_update():
                        logger.info(
                            f"RealtimeAggregationNode [{camera_group_id}] "
                            f"hot-reloaded calibration from {calibration.calibration_path}"
                        )
                        # Coordinate frame may have changed — reset filter + gate + XCoM
                        # tracking, and the body scale with them: every reading in the
                        # fitter's windows was measured in the old frame's units.
                        keypoint_filter.reset()
                        point_gate.reset()
                        prev_com = None
                        prev_com_time = None
                        roll_resolver.reset()
                        body_scale_fitter.reset()
                        skeleton_observability_logged.discard("no_body_scale")

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
                total_body_com: np.ndarray | None = None
                xcom: np.ndarray | None = None
                resolved_pose = None
                mapped_landmarks: dict[str, np.ndarray] = {}
                hydrated_landmarks: dict[str, np.ndarray] = {}
                body_scale_fit: BodyScaleFit | None = None
                reprojected_segment_origins: dict[
                    CameraIdString, dict[TrackedPointNameString, tuple[float, float]]
                ] = {}
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

                    # Convert the triangulated keypoints to Blender once at the source:
                    # the skeleton solve and the wire are Blender-native (+X right, +Y forward, +Z up).
                    raw_keypoints = {name: _to_blender(pos) for name, pos in raw_keypoints.items()}

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
                    if skeleton_fitting_enabled and filtered_keypoints:
                        t0 = time.perf_counter() if timer is not None else 0.0
                        mapped_landmarks = standard_human_mapping(filtered_keypoints)
                        observed = {
                            name: Point.from_array(values=position)
                            for name, position in mapped_landmarks.items()
                        }
                        hydrated_pose = hydrate_skeleton(
                            skeleton=standard_human,
                            observed=observed,
                            require_all=False,
                        )
                        resolved_pose = roll_resolver.resolve_pose(pose=hydrated_pose)
                        hydrated_landmarks = dict(mapped_landmarks)
                        for segment in standard_human.segments.values():
                            if segment.name not in resolved_pose.segment_poses:
                                # Partial hydration: a segment whose landmarks weren't
                                # observed this frame is absent from the pose — skip its
                                # origin rather than indexing a missing segment.
                                continue
                            origin_name = segment.frame_definition.origin_point_name
                            hydrated_landmarks[origin_name] = resolved_pose.segment_poses[segment.name].origin.array
                        # Every hydrated segment already carries its own reading of how big
                        # the subject is — the rigid fit measures it over all of a
                        # segment's landmarks, the direction fit over its one distance —
                        # so the fitter only has to be handed the pose.
                        body_scale_fitter.observe_pose(pose=resolved_pose)
                        if timer is not None:
                            timer.record("skeleton_fitting", (time.perf_counter() - t0) * 1e3)

                    # The rigidifier hands back the hydrated standard-human
                    # landmarks (body + standard-named hands); the solver
                    # consumes them straight through — no bone-keyed map, the
                    # standard human already names every landmark it needs.
                    segment_rotations_world: dict[str, np.ndarray] | None = None
                    segment_rotations_local: dict[str, np.ndarray] | None = None
                    if resolved_pose is not None:
                        t0 = time.perf_counter() if timer is not None else 0.0
                        segment_rotations_world = {
                            name: segment_pose.orientation.as_array()
                            for name, segment_pose in resolved_pose.segment_poses.items()
                        }
                        segment_rotations_local = {}
                        for name, segment_pose in resolved_pose.segment_poses.items():
                            parent_name = rest_pose.parents[name]
                            if (
                                parent_name is None
                                or parent_name not in resolved_pose.segment_poses
                            ):
                                # Root, or a segment whose parent was skipped by partial
                                # hydration — fall back to the world orientation.
                                local = segment_pose.orientation
                            else:
                                local = (
                                    resolved_pose.segment_poses[parent_name].orientation.inverse()
                                    * segment_pose.orientation
                                )
                            segment_rotations_local[name] = local.as_array()
                        if not segment_rotations_world and "empty_orientations" not in skeleton_observability_logged:
                            skeleton_observability_logged.add("empty_orientations")
                            logger.error(
                                "Skeleton solve produced ZERO segment orientations — "
                                "the 3D bones will not render. Rigidified landmarks are "
                                "present, but the solver hydrated no segments."
                            )
                        elif segment_rotations_world and len(segment_rotations_world) < len(standard_human.segments) and "partial_orientations" not in skeleton_observability_logged:
                            skeleton_observability_logged.add("partial_orientations")
                            missing = sorted(set(standard_human.segments) - set(segment_rotations_world))
                            logger.warning(
                                f"Skeleton solve produced {len(segment_rotations_world)}/"
                                f"{len(standard_human.segments)} orientations — unsolved segments: {missing}"
                            )
                        if timer is not None:
                            timer.record("orientation_solve", (time.perf_counter() - t0) * 1e3)

                        # ---- Segment-origin reprojections (the 2D skeleton) ----
                        # Project the fitted skeleton's segment origins back into
                        # each camera — the OVERLAY_REPROJECTIONS layer (larger
                        # dots + connections on the frontend). Only possible with
                        # a valid calibration.
                        if calibration.is_valid:
                            t0 = time.perf_counter() if timer is not None else 0.0
                            reprojected_segment_origins = _reproject_segment_origins(
                                calibration=calibration,
                                standard_human=standard_human,
                                solver_landmarks=hydrated_landmarks,
                            )
                            if timer is not None:
                                timer.record("segment_reprojection", (time.perf_counter() - t0) * 1e3)

                    # ---- Body scale ----
                    # One fit per frame, shared by the center of mass (which places
                    # landmarks from their proportional local positions) and the wire
                    # (which publishes the lengths and the height). `has_body_scale` is
                    # False only while no measurable segment has ever been seen — nobody
                    # in front of the cameras — and then there are no millimetres to
                    # publish, which is said rather than defaulted.
                    if body_scale_fitter.has_body_scale:
                        body_scale_fit = body_scale_fitter.current_fit()
                    elif "no_body_scale" not in skeleton_observability_logged:
                        skeleton_observability_logged.add("no_body_scale")
                        logger.info(
                            "No segment has measured the subject yet, so the skeleton has "
                            "no size — segment lengths and body height stay off the wire "
                            "until a measurable segment is seen. Voting segments: "
                            f"{len(body_scale_fitter.voting_segment_names)}"
                        )

                    # ---- Center of mass ----
                    if (
                        standard_human_mapping is not None
                        and aggregator_config.center_of_mass_enabled
                        and resolved_pose is not None
                        and body_scale_fit is not None
                    ):
                        t0 = time.perf_counter() if timer is not None else 0.0
                        world = landmark_world_positions(
                            skeleton=standard_human,
                            pose=resolved_pose,
                            segment_scales=body_scale_fit.segment_scales,
                        )
                        segment_coms = compute_segment_coms(
                            definitions=com_definitions, world=world
                        )
                        total_body_com = whole_body_center_of_mass(
                            segment_coms=segment_coms, segment_masses=segment_masses
                        )
                        if timer is not None:
                            timer.record("center_of_mass", (time.perf_counter() - t0) * 1e3)

                        # ---- XCoM (extrapolated center of mass) ----
                        if total_body_com is not None:
                            now_com = time.perf_counter()
                            com_z = float(total_body_com[2])
                            if (
                                com_z > 0.0
                                and prev_com is not None
                                and prev_com_time is not None
                            ):
                                dt = now_com - prev_com_time
                                if dt > 0:
                                    com_velocity = (total_body_com - prev_com) / dt
                                    xcom = extrapolated_center_of_mass(
                                        com=total_body_com,
                                        com_velocity=com_velocity,
                                        gravity=GRAVITY_ACCELERATION,
                                    )
                            prev_com = total_body_com.copy()
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
                # Fitted per-segment lengths in millimetres, covering EVERY segment: the
                # ones that were seen carry their own measurement, and the ones that were
                # not are sized by the fitted body height. Empty only while the subject
                # has never been measured at all.
                segment_lengths: dict[str, float] = (
                    dict(body_scale_fit.segment_lengths)
                    if body_scale_fit is not None
                    else {}
                )
                joint_angles = (
                    {
                        joint_name: joint_pose.angles
                        for joint_name, joint_pose in standard_human.compute_joint_poses(
                            pose=resolved_pose
                        ).items()
                    }
                    if resolved_pose is not None
                    else None
                )
                aggregation_output_pub.put(
                    AggregationNodeOutputMessage(
                        frame_number=last_received_frame,
                        pipeline_id=ipc.pipeline_id,
                        pipeline_config=pipeline_config,
                        camera_group_id=camera_group_id,
                        camera_node_outputs=frame_n_outputs,
                        keypoints_arrays=filtered_keypoints,
                        total_body_com=total_body_com,
                        xcom=xcom,
                        standard_skeleton=(hydrated_landmarks if hydrated_landmarks else None),
                        joint_angles=joint_angles,
                        segment_rotations_world=segment_rotations_world,
                        segment_rotations_local=segment_rotations_local,
                        segment_lengths=segment_lengths,
                        body_height_mm=(
                            body_scale_fit.body_height
                            if body_scale_fit is not None
                            else None
                        ),
                        reprojected_segment_origins=reprojected_segment_origins,
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

