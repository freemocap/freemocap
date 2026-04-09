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
import multiprocessing
import time
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import (
    CameraGroupSharedMemory,
    CameraGroupSharedMemoryDTO,
)
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms
from skellyforge.data_models.trajectory_3d import Point3d

from freemocap.core.pipeline.abcs.aggregator_node_abc import AggregatorNode
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import RealtimeAggregatorNodeConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.tasks.calibration.shared.calibration_state import CalibrationStateTracker
from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.bone_length_estimator import AnthropometricPrior
from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.mediapipe_skeleton_config import \
    SkeletonDefinition
from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.realtime_point_gate import RealtimePointGate, \
    GateResult
from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.rigid_body_estimator import RigidBodyPose
from freemocap.core.tasks.mocap.skeleton_dewiggler.realtime_skeleton_filter import RealtimeFilterConfig, \
    RealtimeSkeletonFilter, FilterResult
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
)

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
            worker_registry: WorkerRegistry,
            camera_group_shm_dto: CameraGroupSharedMemoryDTO,
            ipc: PipelineIPC,
            pubsub: PubSubTopicManager,
    ) -> "RealtimeAggregatorNode":
        shutdown_self_flag, worker = cls._create_worker(
            target=cls._run,
            name=f"CameraGroup-{camera_group_id}-AggregationNode",
            worker_registry=worker_registry,
            log_queue=ipc.ws_queue,
            kwargs=dict(
                pipeline_config=config,
                camera_group_id=camera_group_id,
                ipc=ipc,
                camera_group_shm_dto=camera_group_shm_dto,
                camera_node_sub=pubsub.get_subscription(
                    CameraNodeOutputTopic,
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
            ipc: PipelineIPC,
            shutdown_self_flag: multiprocessing.Value,
            camera_group_shm_dto: CameraGroupSharedMemoryDTO,
            camera_node_sub: TopicSubscriptionQueue,
            pipeline_config_sub: TopicSubscriptionQueue,
            process_frame_number_pub: TopicPublicationQueue,
            aggregation_output_pub: TopicPublicationQueue,
    ) -> None:
        logger.debug(f"RealtimeAggregationNode [{camera_group_id}] initializing")
        camera_ids = pipeline_config.camera_ids
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

        camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage | None] = {
            cam_id: None for cam_id in camera_ids
        }
        latest_requested_frame: int = -1
        last_received_frame: int = -1
        last_calibration_poll: float = time.monotonic()
        raw_keypoints: dict[str, np.ndarray] = {}
        filtered_keypoints: dict[str, np.ndarray] = {}
        skeleton_keypoints: dict[str, np.ndarray] = {}
        rigid_body_poses: dict[str, RigidBodyPose] = {}

        try:
            previous_tik = time.perf_counter()
            logger.debug(f"RealtimeAggregationNode [{camera_group_id}] entering main loop")
            while ipc.should_continue and not shutdown_self_flag.value:
                wait_1ms()

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
                if (current_multiframe_number > latest_requested_frame
                        and last_received_frame >= latest_requested_frame):
                    process_frame_number_pub.put(
                        ProcessFrameNumberMessage(
                            frame_number=current_multiframe_number,
                        ),
                    )
                    latest_requested_frame = current_multiframe_number

                # ---- Collect camera node outputs ----
                if camera_node_sub.empty():
                    continue

                cam_output: CameraNodeOutputMessage = camera_node_sub.get()
                if cam_output.camera_id not in camera_ids:
                    raise ValueError(
                        f"Camera ID {cam_output.camera_id} not in "
                        f"camera IDs {list(camera_ids)}"
                    )
                camera_node_outputs[cam_output.camera_id] = cam_output

                # ---- Check if all cameras reported for this frame ----
                if not all(
                        isinstance(v, CameraNodeOutputMessage)
                        for v in camera_node_outputs.values()
                ):
                    continue

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

                # ---- Triangulate and process if calibration is valid ----
                # All processing stays in dict[str, ndarray] until final
                # conversion to Point3d for the output message.

                if calibration.is_valid and aggregator_config.triangulation_enabled:
                    # Triangulate mediapipe observations
                    mediapipe_observations_by_camera = {
                        cam_id: output.mediapipe_observation
                        for cam_id, output in camera_node_outputs.items()
                        if isinstance(output, CameraNodeOutputMessage)
                           and output.mediapipe_observation is not None
                    }
                    if mediapipe_observations_by_camera:
                        _merge_triangulated_arrays(
                            triangulated=calibration.try_triangulate(
                                frame_number=latest_requested_frame,
                                frame_observations_by_camera=mediapipe_observations_by_camera,
                                max_reprojection_error_px=filter_config.max_reprojection_error_px,
                            ),
                            into=raw_keypoints,
                        )

                    # Triangulate charuco observations
                    charuco_observations_by_camera = {
                        cam_id: output.charuco_observation
                        for cam_id, output in camera_node_outputs.items()
                        if isinstance(output, CameraNodeOutputMessage)
                           and output.charuco_observation is not None
                    }
                    if charuco_observations_by_camera:
                        _merge_triangulated_arrays(
                            triangulated=calibration.try_triangulate(
                                frame_number=latest_requested_frame,
                                frame_observations_by_camera=charuco_observations_by_camera,
                                max_reprojection_error_px=filter_config.max_reprojection_error_px,
                            ),
                            into=raw_keypoints,
                        )

                    # Velocity gate: reject teleportation spikes
                    if aggregator_config.filter_enabled:
                        if raw_keypoints:
                            gate_result: GateResult = point_gate.gate(
                                t=time.monotonic(),
                                points=raw_keypoints,
                            )
                            _merge_triangulated_arrays(
                                triangulated=gate_result.positions,
                                into=filtered_keypoints,
                            )

                        # # Filter + constrain skeleton keypoints
                        # if filtered_keypoints and config.skeleton_enabled:
                        #     filtered_keypoints = _filter_skeleton_arrays(
                        #         point_arrays=filtered_keypoints,
                        #         skeleton_filter=skeleton_filter,
                        #         t=time.monotonic(),
                        #     )

                    # # Estimate rigid body segment poses
                    # if filtered_keypoints and config.skeleton_enabled and skeleton_filter.current_bone_lengths:
                    #     skeleton_trajectories = estimate_rigid_bodies(
                    #         positions=filtered_keypoints,
                    #         skeleton=skeleton_filter.skeleton,
                    #         bone_lengths=skeleton_filter.current_bone_lengths,
                    #     )

                # Convert to Point3d once at the end for the output message

                now = time.perf_counter()
                loop_time = now - previous_tik
                previous_tik = now
                # logger.trace(f"RealtimeAggregationNode [{camera_group_id}] loop time: {loop_time*1e3:.3f} ms")

                # ---- Publish aggregated output ----
                aggregation_output_pub.put(
                    AggregationNodeOutputMessage(
                        frame_number=latest_requested_frame,
                        pipeline_id=ipc.pipeline_id,
                        pipeline_config=pipeline_config,
                        camera_group_id=camera_group_id,
                        camera_node_outputs=camera_node_outputs,
                        raw_keypoints=_arrays_to_point3d(raw_keypoints),
                        filtered_keypoints=_arrays_to_point3d(filtered_keypoints),
                        # rigid_body_poses=rigid_body_poses,
                    ),
                )

                camera_node_outputs = {cam_id: None for cam_id in pipeline_config.camera_configs.keys()}

        except Exception as e:
            logger.error(
                f"Exception in RealtimeAggregationNode [{camera_group_id}]: {e}",
                exc_info=True,
            )
            ipc.kill_everything()
            raise
        finally:
            logger.debug(f"RealtimeAggregationNode [{camera_group_id}] exiting")
