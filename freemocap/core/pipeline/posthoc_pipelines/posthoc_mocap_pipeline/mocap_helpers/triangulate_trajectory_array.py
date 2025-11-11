import logging
from typing import Any
import numpy as np
from pydantic import BaseModel

from skellyforge.data_models.data_3d import Observation3d, Trajectory3d
from skellyforge.data_models.frame_group import CameraIdString, FrameGroup, Trajectory2dGroup

from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.calibration_helpers.freemocap_anipose import \
    AniposeCameraGroup

logger = logging.getLogger(__name__)


class TriangulationConfig(BaseModel):
    use_ransac: bool = False


def triangulate_array(
    data_2d: np.ndarray, # shape: cameras × frames × points × 2
    camera_group: AniposeCameraGroup,
    config: TriangulationConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    number_of_cameras = data_2d.shape[0]
    number_of_frames = data_2d.shape[1]
    number_of_tracked_points = data_2d.shape[2]
    number_of_spatial_dimensions = data_2d.shape[3]

    if number_of_spatial_dimensions != 2:
        logger.error(
            f"Expected 2D data but got {number_of_spatial_dimensions} dimensions"
        )
        raise ValueError("Input data must have 2 spatial dimensions")

    data2d_flat = data_2d.reshape(number_of_cameras, -1, 2)

    logger.info(f"shape of data2d_flat: {data2d_flat.shape}")

    # Triangulate 2D points to 3D
    if config.use_ransac:
        logger.info("Using RANSAC triangulation method")
        triangulated_data_flat = camera_group.triangulate_ransac(
            data2d_flat, progress=True, kill_event=None
        )
    else:
        logger.info("Using standard triangulation method")
        triangulated_data_flat = camera_group.triangulate(
            data2d_flat, progress=False, kill_event=None
        )

    if triangulated_data_flat is None:
        raise ValueError("Triangulation stopped due to kill event")

    # Reshape to frames × points × xyz
    triangulated_data = triangulated_data_flat.reshape(
        number_of_frames, number_of_tracked_points, 3
    )

    # Calculate reprojection errors
    reprojection_error_full = camera_group.reprojection_error(
        triangulated_data_flat, data2d_flat
    )
    reprojection_error_flat = camera_group.calculate_mean_reprojection_error(
        reprojection_error_full
    )

    # Reshape reprojection errors
    reprojection_error_by_camera = np.linalg.norm(
        reprojection_error_full, axis=2
    ).reshape(number_of_cameras, number_of_frames, number_of_tracked_points)
    reprojection_error = reprojection_error_flat.reshape(
        number_of_frames, number_of_tracked_points
    )

    return triangulated_data, reprojection_error, reprojection_error_by_camera


def triangulate_frame_group(
    frame_number: int,
    frame_group: FrameGroup,
    camera_group: AniposeCameraGroup,
    config: TriangulationConfig,
) -> Observation3d:
    camera_group = subset_camera_names(data_dict=frame_group, camera_group=camera_group)

    ordered_frame_group = preserve_camera_group_order(data_dict=frame_group, camera_group=camera_group)

    data_2d = np.stack(
        [observation.to_array for observation in ordered_frame_group.values()],
        axis=0,
    )

    if len(frame_group) != data_2d.shape[0]:
        logger.error(
            f"Expected {len(frame_group)} cameras but got {data_2d.shape[0]} cameras"
        )
        raise ValueError(
            "Input data must have the same number of cameras as the camera group"
        )
    
    triangulated_data, reprojection_error, reprojection_error_by_camera = triangulate_array(
        data_2d, camera_group, config
    )


    return Observation3d(
        frame_number=frame_number,
        triangulated_data=triangulated_data,
        reprojection_error=reprojection_error,
        reprojection_error_by_camera=reprojection_error_by_camera,
    )


def triangulate_frame_groups(
    frame_groups: dict[int, FrameGroup],
    camera_group: AniposeCameraGroup,
    config: TriangulationConfig,
) -> Trajectory3d:
    observations_3d = []
    frame_groups = dict(sorted(frame_groups.items()))
    for frame_number, frame_group in frame_groups.items():
        observations_3d.append(triangulate_frame_group(
            frame_number, frame_group, camera_group, config
        ))
    return Trajectory3d.from_observations(list(frame_groups.values()))


def triangulate_trajectories(
    trajectory_group: Trajectory2dGroup,
    camera_group: AniposeCameraGroup,
    config: TriangulationConfig,
):
    # TODO: move this validation into Trajectory2dGroup creation
    if len(set(trajectory.start_frame for trajectory in trajectory_group.values())) != 1:
        raise ValueError(
            "Input data must have the same start frame for all trajectories"
    )
    if len(set(trajectory.end_frame for trajectory in trajectory_group.values())) != 1:
        raise ValueError(
            "Input data must have the same end frame for all trajectories"
    )
    camera_group = subset_camera_names(data_dict=trajectory_group, camera_group=camera_group)
    ordered_trajectory_group = preserve_camera_group_order(data_dict=trajectory_group, camera_group=camera_group)

    data_2d = np.stack(
        [trajectory.points2d for trajectory in ordered_trajectory_group.values()],
        axis=0
    )

    if len(trajectory_group) != data_2d.shape[0]:
        logger.error(
            f"Expected {len(trajectory_group)} cameras but got {data_2d.shape[0]} cameras"
        )
        raise ValueError(
            "Input data must have the same number of cameras as the camera group"
        )
    
    triangulated_data, reprojection_error, reprojection_error_by_camera = triangulate_array(
        data_2d, camera_group, config
    )

    start_frame = list(trajectory_group.values())[0].start_frame
    end_frame = list(trajectory_group.values())[0].end_frame

    return Trajectory3d(
        start_frame=start_frame,
        end_frame=end_frame,
        triangulated_data=triangulated_data,
        reprojection_error=reprojection_error,
        reprojection_error_by_camera=reprojection_error_by_camera,
    )

def triangulate_dict(
    data_dict: dict[CameraIdString, np.ndarray],
    camera_group: AniposeCameraGroup,
    config: TriangulationConfig,
    start_frame: int | None = None,
    end_frame: int | None = None,
) -> Trajectory3d:
    camera_group = subset_camera_names(
        data_dict=data_dict, camera_group=camera_group
    )

    ordered_data_dict = preserve_camera_group_order(data_dict=data_dict, camera_group=camera_group)

    combined_2d_data = np.stack(
        [observation for observation in ordered_data_dict.values()],
        axis=0
    )
    logger.info(f"shape of combined_2d_data: {combined_2d_data.shape}")

    triangulated_data, reprojection_error, reprojection_error_by_camera = triangulate_array(
        combined_2d_data, camera_group, config
    )
    if start_frame is None:
        start_frame = 0
    if end_frame is None:
        end_frame = combined_2d_data.shape[1]
    return Trajectory3d(
        start_frame=start_frame,
        end_frame=end_frame,
        triangulated_data=triangulated_data,
        reprojection_error=reprojection_error,
        reprojection_error_by_camera=reprojection_error_by_camera,
    )

    
def subset_camera_names(data_dict: dict[CameraIdString, Any], camera_group: AniposeCameraGroup):
    valid_calibration_names = []
    for camera in camera_group.cameras:
        for key in data_dict.keys():
            if camera.name in key:
                valid_calibration_names.append(camera.name)
                break
    if len(valid_calibration_names) != len(data_dict.keys()):
        raise ValueError(
            "Camera names in frame group do not match camera names in camera group. Make sure calibration matches input data."
        )
    if len(valid_calibration_names) == len(camera_group.cameras):
        return camera_group
    logger.warning(
        f"Frame group is missing cameras from camera group, triangulating with only cameras in frame group: {valid_calibration_names}"
    )
    return camera_group.subset_cameras_names(valid_calibration_names)


def preserve_camera_group_order(data_dict: dict[CameraIdString, Any], camera_group: AniposeCameraGroup) -> dict[CameraIdString, Any]:
    ordered_data_dict = {}

    for camera in camera_group.cameras:
        for name, data in data_dict.items():
            if camera.name in name:
                ordered_data_dict[name] = data
                break

    logger.info(f"camera group names: {[camera.name for camera in camera_group.cameras]}")
    logger.info(f"ordered data dict names: {[name for name in ordered_data_dict.keys()]}")

    return ordered_data_dict