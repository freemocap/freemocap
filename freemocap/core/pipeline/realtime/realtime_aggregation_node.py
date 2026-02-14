"""
RealtimeAggregationNode: collects per-camera observations for each frame,
triangulates mediapipe and charuco observations (if calibration is valid),
filters+constrains the triangulated skeleton via One Euro + FABRIK,
and publishes aggregated output.

Uses CalibrationStateTracker for graceful degradation: if triangulation fails,
the calibration is invalidated and we continue publishing 2D-only data until
a new calibration is loaded (triggered by a config update after posthoc
calibration completes).

Skeleton filtering (One Euro + FABRIK) runs on the triangulated 3D mediapipe
points. Bone lengths are estimated online from observed inter-keypoint distances
blended with an anthropometric prior. The filter resets on calibration reload
since the coordinate frame may change.
"""
import logging
import multiprocessing
import time
from dataclasses import dataclass

import numpy as np
from skellycam.core.ipc.process_management.process_registry import ProcessRegistry
from skellyforge.data_models.trajectory_3d import Point3d
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import (
    CameraGroupSharedMemory,
    CameraGroupSharedMemoryDTO,
)
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms

from freemocap.core.calibration.shared.calibration_state import CalibrationStateTracker
from freemocap.core.mocap.skeleton_dewiggler.dewiggling_methods.bone_length_estimator import AnthropometricPrior
from freemocap.core.mocap.skeleton_dewiggler.dewiggling_methods.mediapipe_skeleton_config import SkeletonDefinition
from freemocap.core.mocap.skeleton_dewiggler.dewiggling_methods.realtime_point_gate import RealtimePointGate
from freemocap.core.mocap.skeleton_dewiggler.realtime_skeleton_filter import RealtimeFilterConfig, \
    RealtimeSkeletonFilter

from freemocap.core.pipeline.base_node import BaseNode
from freemocap.core.pipeline.pipeline_configs import RealtimePipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
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
    ShouldCalibrateTopic,
)

logger = logging.getLogger(__name__)


def _merge_triangulated_points(
    *,
    triangulated: dict[str, np.ndarray] | None,
    into: dict[str, Point3d],
) -> None:
    """Merge triangulated 3D points into the output dict, skipping NaN entries."""
    if triangulated is None:
        return
    for point_name, coords in triangulated.items():
        if isinstance(coords, np.ndarray):
            if np.any(np.isnan(coords)):
                continue
            into[point_name] = Point3d(
                x=float(coords[0]),
                y=float(coords[1]),
                z=float(coords[2]),
            )
        elif isinstance(coords, Point3d):
            into[point_name] = coords
        else:
            raise TypeError(
                f"Unexpected type for triangulated point '{point_name}': "
                f"{type(coords).__name__}"
            )


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


def _filter_skeleton_points(
    *,
    tracked_points3d: dict[str, Point3d],
    skeleton_filter: RealtimeSkeletonFilter,
    t: float,
) -> dict[str, Point3d]:
    """
    Run the skeleton filter on triangulated points, returning filtered results.

    Only skeleton keypoints are filtered+constrained. Non-skeleton points
    (e.g. charuco board corners) are passed through unchanged.
    """
    skeleton_keypoint_names = skeleton_filter.skeleton.keypoint_names

    # Extract skeleton keypoints as numpy arrays
    skeleton_positions: dict[str, np.ndarray] = {}
    for name, point in tracked_points3d.items():
        if name in skeleton_keypoint_names:
            skeleton_positions[name] = np.array([point.x, point.y, point.z], dtype=np.float64)

    if not skeleton_positions:
        return tracked_points3d

    # Run the filter
    filtered_positions = skeleton_filter.process_frame(
        t=t,
        positions=skeleton_positions,
    )

    # Build output: filtered skeleton points + unmodified non-skeleton points
    result: dict[str, Point3d] = {}
    for name, point in tracked_points3d.items():
        if name in filtered_positions:
            coords = filtered_positions[name]
            result[name] = Point3d(
                x=float(coords[0]),
                y=float(coords[1]),
                z=float(coords[2]),
            )
        else:
            result[name] = point

    return result


@dataclass
class RealtimeAggregationNode(BaseNode):

    @classmethod
    def create(
        cls,
        *,
        config: RealtimePipelineConfig,
        camera_group_id: CameraGroupIdString,
        process_registry: ProcessRegistry,
        camera_group_shm_dto: CameraGroupSharedMemoryDTO,
        ipc: PipelineIPC,
        pubsub: PubSubTopicManager,
    ) -> "RealtimeAggregationNode":
        shutdown_self_flag, worker = cls._create_worker(
            target=cls._run,
            name=f"CameraGroup-{camera_group_id}-AggregationNode",
            process_registry=process_registry,
            log_queue=ipc.ws_queue,
            kwargs=dict(
                config=config,
                camera_group_id=camera_group_id,
                ipc=ipc,
                camera_group_shm_dto=camera_group_shm_dto,
                camera_node_sub=pubsub.get_subscription(
                    CameraNodeOutputTopic,
                ),
                pipeline_config_sub=pubsub.get_subscription(
                    PipelineConfigUpdateTopic,
                ),
                should_calibrate_sub=pubsub.get_subscription(
                    ShouldCalibrateTopic,
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
        config: RealtimePipelineConfig,
        camera_group_id: CameraGroupIdString,
        ipc: PipelineIPC,
        shutdown_self_flag: multiprocessing.Value,
        camera_group_shm_dto: CameraGroupSharedMemoryDTO,
        camera_node_sub: TopicSubscriptionQueue,
        pipeline_config_sub: TopicSubscriptionQueue,
        should_calibrate_sub: TopicSubscriptionQueue,
        process_frame_number_pub: TopicPublicationQueue,
        aggregation_output_pub: TopicPublicationQueue,
    ) -> None:
        logger.debug(f"RealtimeAggregationNode [{camera_group_id}] initializing")

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
        filter_config = config.mocap_config.skeleton_filter
        skeleton_filter = _create_skeleton_filter(filter_config=filter_config)

        # Initialize velocity gate for rejecting teleportation spikes
        point_gate = RealtimePointGate(
            max_velocity_m_per_s=filter_config.max_velocity_m_per_s,
            max_rejected_streak=filter_config.max_rejected_streak,
        )

        camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage | None] = {
            cam_id: None for cam_id in config.camera_configs.keys()
        }
        latest_requested_frame: int = -1
        last_received_frame: int = -1

        try:
            logger.debug(f"RealtimeAggregationNode [{camera_group_id}] entering main loop")
            while ipc.should_continue and not shutdown_self_flag.value:
                wait_1ms()

                # ---- Handle config updates (also triggers calibration reload) ----
                while not pipeline_config_sub.empty():
                    msg: PipelineConfigUpdateMessage = pipeline_config_sub.get()
                    config = msg.pipeline_config
                    logger.info(
                        f"RealtimeAggregationNode [{camera_group_id}] received config update"
                    )
                    if calibration.reload():
                        logger.info(
                            f"RealtimeAggregationNode [{camera_group_id}] "
                            f"reloaded calibration from {calibration.calibration_path}"
                        )
                        # Reset filter + gate state — coordinate frame may have changed
                        skeleton_filter.reset()
                        point_gate.reset()
                        logger.info(
                            f"RealtimeAggregationNode [{camera_group_id}] "
                            f"reset skeleton filter and point gate after calibration reload"
                        )

                # ---- Handle explicit calibration signals ----
                while not should_calibrate_sub.empty():
                    should_calibrate_sub.get()
                    if calibration.reload():
                        logger.info(
                            f"RealtimeAggregationNode [{camera_group_id}] "
                            f"reloaded calibration after ShouldCalibrate signal"
                        )
                        skeleton_filter.reset()
                        point_gate.reset()
                        logger.info(
                            f"RealtimeAggregationNode [{camera_group_id}] "
                            f"reset skeleton filter and point gate after calibration reload"
                        )

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
                if cam_output.camera_id not in config.camera_configs:
                    raise ValueError(
                        f"Camera ID {cam_output.camera_id} not in "
                        f"camera IDs {list(config.camera_configs.keys())}"
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
                    raise ValueError(
                        f"Frame number mismatch across cameras: {frame_numbers} "
                        f"(expected {latest_requested_frame})"
                    )

                last_received_frame = latest_requested_frame

                # ---- Triangulate mediapipe and charuco observations if calibration is valid ----
                tracked_points3d: dict[str, Point3d] = {}
                if calibration.is_valid:
                    # Triangulate mediapipe observations
                    mediapipe_observations_by_camera = {
                        cam_id: output.mediapipe_observation
                        for cam_id, output in camera_node_outputs.items()
                        if isinstance(output, CameraNodeOutputMessage)
                        and output.mediapipe_observation is not None
                    }
                    if mediapipe_observations_by_camera:
                        _merge_triangulated_points(
                            triangulated=calibration.try_triangulate(
                                frame_number=latest_requested_frame,
                                frame_observations_by_camera=mediapipe_observations_by_camera,
                                max_reprojection_error_px=filter_config.max_reprojection_error_px,
                            ),
                            into=tracked_points3d,
                        )

                    # Triangulate charuco observations
                    charuco_observations_by_camera = {
                        cam_id: output.charuco_observation
                        for cam_id, output in camera_node_outputs.items()
                        if isinstance(output, CameraNodeOutputMessage)
                        and output.charuco_observation is not None
                    }
                    if charuco_observations_by_camera:
                        _merge_triangulated_points(
                            triangulated=calibration.try_triangulate(
                                frame_number=latest_requested_frame,
                                frame_observations_by_camera=charuco_observations_by_camera,
                                max_reprojection_error_px=filter_config.max_reprojection_error_px,
                            ),
                            into=tracked_points3d,
                        )

                    # ---- Velocity gate: reject teleportation spikes ----
                    if tracked_points3d:
                        raw_arrays: dict[str, np.ndarray] = {
                            name: np.array([pt.x, pt.y, pt.z], dtype=np.float64)
                            for name, pt in tracked_points3d.items()
                        }
                        gated_arrays = point_gate.gate(
                            t=time.monotonic(),
                            points=raw_arrays,
                        )
                        # Rebuild tracked_points3d with only gated points
                        tracked_points3d = {
                            name: Point3d(
                                x=float(arr[0]),
                                y=float(arr[1]),
                                z=float(arr[2]),
                            )
                            for name, arr in gated_arrays.items()
                        }

                    # ---- Filter + constrain skeleton keypoints ----
                    if tracked_points3d:
                        tracked_points3d = _filter_skeleton_points(
                            tracked_points3d=tracked_points3d,
                            skeleton_filter=skeleton_filter,
                            t=time.monotonic(),
                        )

                # ---- Publish aggregated output ----
                aggregation_output_pub.put(
                    AggregationNodeOutputMessage(
                        frame_number=latest_requested_frame,
                        pipeline_id=ipc.pipeline_id,
                        camera_group_id=camera_group_id,
                        pipeline_config=config,
                        camera_node_outputs=camera_node_outputs,
                        tracked_points3d=tracked_points3d,
                    ),
                )

                camera_node_outputs = {cam_id: None for cam_id in config.camera_configs.keys()}

        except Exception as e:
            logger.error(
                f"Exception in RealtimeAggregationNode [{camera_group_id}]: {e}",
                exc_info=True,
            )
            ipc.kill_everything()
            raise
        finally:
            logger.debug(f"RealtimeAggregationNode [{camera_group_id}] exiting")