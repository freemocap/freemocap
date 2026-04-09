import logging
from typing import Any

import numpy as np
from pydantic import BaseModel
from skellyforge.data_models.trajectory_3d import Observation3d, Trajectory3d
from skellyforge.data_models.type_overloads import CameraIdString, FrameObservationsByCamera, Trajectory2dGroup
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation

from freemocap.core.tasks.calibration.anipose_calibration.helpers.freemocap_anipose import AniposeCameraGroup

logger = logging.getLogger(__name__)


class TriangulationConfig(BaseModel):
    use_ransac: bool = False


def triangulate_array(
        data2d_cam_id_xy: np.ndarray,  # shape: cameras × frames × points × 2
        camera_group: AniposeCameraGroup,
        config: TriangulationConfig,
        calculate_reprojection_error: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    number_of_cameras = data2d_cam_id_xy.shape[0]
    number_of_frames = data2d_cam_id_xy.shape[1]
    number_of_tracked_points = data2d_cam_id_xy.shape[2]
    number_of_spatial_dimensions = data2d_cam_id_xy.shape[3]

    if number_of_spatial_dimensions == 3:
        # if provided 3d, ignore z dimension
        data2d_cam_id_xy = data2d_cam_id_xy[..., :2]

    data2d_flat = data2d_cam_id_xy.reshape(number_of_cameras, -1, 2)


    # Triangulate 2D points to 3D
    if config.use_ransac:
        logger.info("Using RANSAC triangulation method")
        triangulated_data_flat = camera_group.triangulate_ransac(
            data2d_flat, progress=True, kill_event=None
        )
    else:
        triangulated_data_flat = camera_group.triangulate(
            data2d_flat, progress=False, kill_event=None
        )

    triangulated3d_fr_id_xyz = triangulated_data_flat.reshape(
        number_of_frames, number_of_tracked_points, 3
    )

    # Calculate reprojection error
    reprojection_error_by_camera = camera_group.reprojection_error(
        triangulated3d_fr_id_xyz.reshape(-1, 3),
        data2d_flat,
        mean=False,
    )
    reprojection_error_flat = np.mean(np.linalg.norm(reprojection_error_by_camera, axis=2), axis=0)
    reprojection_error = reprojection_error_flat.reshape(
        number_of_frames, number_of_tracked_points
    )

    return triangulated3d_fr_id_xyz, reprojection_error, reprojection_error_by_camera


def triangulate_frame_observations(frame_number: int,
                                   frame_observations_by_camera: FrameObservationsByCamera,
                                   anipose_camera_group: AniposeCameraGroup,
                                   config: TriangulationConfig=TriangulationConfig(),
                                   calculate_reprojection_error: bool = False
                                   ) -> Observation3d:
    anipose_camera_group = subset_camera_names(data_dict=frame_observations_by_camera, anipose_camera_group=anipose_camera_group)

    ordered_frame_observations = preserve_camera_group_order(data_by_camera=frame_observations_by_camera,
                                                             camera_group=anipose_camera_group)

    if not all([isinstance(obs, BaseObservation) for obs in ordered_frame_observations.values()]):
        raise TypeError("All values in frame_observations_by_camera must be BaseObservation instances")
    data2d_stack_list = [obs.to_2d_array() for obs in ordered_frame_observations.values()]
    if not len(set(data.shape for data in data2d_stack_list)) == 1:
        raise ValueError(f"2d data from each camera must be the same shape- got: {[data.shape for data in data2d_stack_list]}")
    data2d_cam_id_xy = np.stack(data2d_stack_list, axis=0)

    if len(frame_observations_by_camera) != data2d_cam_id_xy.shape[0]:
        logger.error(
            f"Expected {len(frame_observations_by_camera)} cameras but got {data2d_cam_id_xy.shape[0]} cameras"
        )
        raise ValueError(
            "Input data must have the same number of cameras as the camera group"
        )
    # add singleton frame dimension
    data2d_cam_fr_id_xyz = data2d_cam_id_xy.reshape((data2d_cam_id_xy.shape[0], 1, data2d_cam_id_xy.shape[1], data2d_cam_id_xy.shape[2]))
    triangulated_data, _, _ = triangulate_array(
        data2d_cam_id_xy=data2d_cam_fr_id_xyz,
        camera_group=anipose_camera_group,
        config=config,
        calculate_reprojection_error=calculate_reprojection_error,
    )

    rotated_triangulated = rotate_by_180_deg_about_x(triangulated_data)

    # Get names from the PointCloud — structurally guaranteed to match
    # to_2d_array() row order because both read from the same object.
    first_obs = next(iter(frame_observations_by_camera.values()))
    point_names = list(first_obs.points.names)

    return Observation3d(
        frame_number=frame_number,
        triangulated_data=np.squeeze(rotated_triangulated),
        names=point_names,
    )

def rotate_by_180_deg_about_x(points_3d: np.ndarray) -> np.ndarray:
    rotation_matrix = np.array([[1, 0, 0],
                                [0, -1, 0],
                                [0, 0, -1]])
    rotated_points = points_3d @ rotation_matrix.T
    return rotated_points

def triangulate_frame_groups(
        frame_groups: dict[int, FrameObservationsByCamera],
        camera_group: AniposeCameraGroup,
        config: TriangulationConfig,
) -> Trajectory3d:
    observations_3d = []
    frame_groups = dict(sorted(frame_groups.items()))
    for frame_number, frame_group in frame_groups.items():
        observation_3d = triangulate_frame_observations(
            frame_number=frame_number,
            frame_observations_by_camera=frame_group,
            anipose_camera_group=camera_group,
            config=config,
        )
        observations_3d.append(observation_3d)
    return Trajectory3d.from_observations(observations_3d)


def triangulate_dict(
        data2d_fr_mar_xy_by_camera: dict[CameraIdString, np.ndarray],
        camera_group: AniposeCameraGroup,
        config: TriangulationConfig = TriangulationConfig(),
        start_frame: int | None = None,
        end_frame: int | None = None,
) -> Trajectory3d:
    """Triangulate pre-stacked 2D arrays (one per camera) into a 3D trajectory."""
    camera_group = subset_camera_names(
        data_dict=data2d_fr_mar_xy_by_camera, anipose_camera_group=camera_group
    )

    ordered_data_dict: dict[CameraIdString, object] = preserve_camera_group_order(
        data_by_camera=data2d_fr_mar_xy_by_camera, camera_group=camera_group
    )
    stacked_2d_data_list = []
    for camera_id, data2d_fr_mar_xy in ordered_data_dict.items():
        if any([not isinstance(d, np.ndarray) for d in ordered_data_dict.values()]):
            raise TypeError("All values in data2d_fr_mar_xy_by_camera must be numpy arrays")
        if len(data2d_fr_mar_xy.shape) != 3:
            raise ValueError(
                f"Input data arrays must have shape (frames, markers, 2) — "
                f"got shape {data2d_fr_mar_xy.shape} for camera {camera_id}"
            )
        if data2d_fr_mar_xy.shape[2] != 2:
            raise ValueError(
                f"Input data arrays must have last dimension of size 2 — "
                f"got size {data2d_fr_mar_xy.shape[2]} for camera {camera_id}"
            )
        stacked_2d_data_list.append(data2d_fr_mar_xy)

    data2d_camera_fr_mar_xy = np.stack(stacked_2d_data_list, axis=0)
    logger.info(f"shape of combined_2d_data: {data2d_camera_fr_mar_xy.shape}")

    triangulated_data, reprojection_error, reprojection_error_by_camera = triangulate_array(
        data2d_camera_fr_mar_xy, camera_group, config
    )
    if start_frame is None:
        start_frame = 0
    if end_frame is None:
        end_frame = data2d_camera_fr_mar_xy.shape[1]
    return Trajectory3d(
        start_frame=start_frame,
        end_frame=end_frame,
        triangulated_data=triangulated_data,
        reprojection_error=reprojection_error,
        reprojection_error_by_camera=reprojection_error_by_camera,
    )


def triangulate_trajectories(
        trajectories_2d: Trajectory2dGroup,
        camera_group: AniposeCameraGroup,
        config: TriangulationConfig = TriangulationConfig(),
) -> Trajectory3d:
    return triangulate_frame_groups(
        frame_groups=trajectories_2d.as_frame_groups(),
        camera_group=camera_group,
        config=config,
    )


def subset_camera_names(data_dict: dict, anipose_camera_group: AniposeCameraGroup) -> AniposeCameraGroup:
    valid_calibration_names = []
    for camera in anipose_camera_group.cameras:
        for key in data_dict.keys():
            if camera.name in key:
                valid_calibration_names.append(camera.name)
                break
    if len(valid_calibration_names) != len(data_dict.keys()):
        raise ValueError(
            f"Camera names in frame group do not match camera names in camera group. "
            f"Make sure calibration matches input data. "
            f"Expected: {valid_calibration_names}, got: {list(data_dict.keys())}"
        )
    if len(valid_calibration_names) == len(anipose_camera_group.cameras):
        return anipose_camera_group
    logger.warning(
        f"Frame group is missing cameras from camera group, "
        f"triangulating with only cameras in frame group: {valid_calibration_names}"
    )
    return anipose_camera_group.subset_cameras_names(valid_calibration_names)


def preserve_camera_group_order(
        data_by_camera: dict[str, Any],
        camera_group: AniposeCameraGroup,
) -> dict[str, Any]:
    """Reorder the data dict to match the camera group's camera order."""
    ordered_data_dict = {}
    for camera in camera_group.cameras:
        for camera_id, data in data_by_camera.items():
            if camera.name in camera_id:
                ordered_data_dict[camera_id] = data
                break
    return ordered_data_dict
