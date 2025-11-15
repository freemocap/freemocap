import logging
from typing import Any

import numpy as np
from pydantic import BaseModel
from skellyforge.data_models.trajectory_3d import Observation3d, Trajectory3d
from skellyforge.data_models.type_overloads import CameraIdString, FrameObservationsByCamera, Trajectory2dGroup

from skellytracker.trackers.base_tracker.base_tracker_abcs import  BaseObservation
from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.calibration_helpers.freemocap_anipose import \
    AniposeCameraGroup

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

    if triangulated_data_flat is None:
        raise ValueError("Triangulation stopped due to kill event")

    # Reshape to frames × points × xyz
    triangulated3d_fr_id_xyz = triangulated_data_flat.reshape(
        number_of_frames, number_of_tracked_points, 3
    )

    if not calculate_reprojection_error:
        return triangulated3d_fr_id_xyz, np.array([]), np.array([])
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
    return Observation3d(
        frame_number=frame_number,
        triangulated_data=np.squeeze(triangulated_data),
        names=list(frame_observations_by_camera.values())[0].to_tracked_points().keys(),
        # reprojection_error=reprojection_error,
        # reprojection_error_by_camera=reprojection_error_by_camera,
    )


def triangulate_frame_groups(
        frame_groups: dict[int, FrameObservationsByCamera],
        camera_group: AniposeCameraGroup,
        config: TriangulationConfig,
) -> Trajectory3d:
    observations_3d = []
    frame_groups = dict(sorted(frame_groups.items()))
    for frame_number, frame_group in frame_groups.items():
        observations_3d.append(triangulate_frame_observations(
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
    camera_group = subset_camera_names(data_dict=trajectory_group, anipose_camera_group=camera_group)
    ordered_trajectory_group = preserve_camera_group_order(data_by_camera=trajectory_group, camera_group=camera_group)

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
        data2d_fr_mar_xy_by_camera: dict[CameraIdString, np.ndarray],
        camera_group: AniposeCameraGroup,
        config: TriangulationConfig = TriangulationConfig(),
        start_frame: int | None = None,
        end_frame: int | None = None,
) -> Trajectory3d:
    camera_group = subset_camera_names(
        data_dict=data2d_fr_mar_xy_by_camera, anipose_camera_group=camera_group
    )

    ordered_data_dict:dict[CameraIdString,object] = preserve_camera_group_order(data_by_camera=data2d_fr_mar_xy_by_camera, camera_group=camera_group)
    stacked_2d_data_list = []
    for camera_id, data2d_fr_mar_xy in ordered_data_dict.items():
        if any([not isinstance(data2d_fr_mar_xy, np.ndarray) for data2d_fr_mar_xy in ordered_data_dict.values()]):
            raise TypeError("All values in data2d_fr_mar_xy_by_camera must be numpy arrays")
        if len(data2d_fr_mar_xy.shape) != 3:
            logger.error(
                f"Expected 3D array for camera {camera_id} but got array with shape {data2d_fr_mar_xy.shape}"
            )
            raise ValueError(
                "Input data arrays must have shape (frames, markers, 2)"
            )
        if data2d_fr_mar_xy.shape[2] != 2:
            logger.error(
                f"Expected last dimension of size 2 for camera {camera_id} but got size {data2d_fr_mar_xy.shape[2]}"
            )
            raise ValueError(
                "Input data arrays must have shape (frames, markers, 2)"
            )
        stacked_2d_data_list.append(data2d_fr_mar_xy)

    data2d_camera_fr_mar_xy = np.stack(stacked_2d_data_list,axis=0)
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


def subset_camera_names(data_dict: dict[CameraIdString, Any], anipose_camera_group: AniposeCameraGroup)->AniposeCameraGroup:
    valid_calibration_names = []
    for camera in anipose_camera_group.cameras:
        for key in data_dict.keys():
            if camera.name in key:
                valid_calibration_names.append(camera.name)
                break
    if len(valid_calibration_names) != len(data_dict.keys()):
        raise ValueError(
            "Camera names in frame group do not match camera names in camera group. Make sure calibration matches input data."
        )
    if len(valid_calibration_names) == len(anipose_camera_group.cameras):
        return anipose_camera_group
    logger.warning(
        f"Frame group is missing cameras from camera group, triangulating with only cameras in frame group: {valid_calibration_names}"
    )
    return anipose_camera_group.subset_cameras_names(valid_calibration_names)


def preserve_camera_group_order(data_by_camera: dict[CameraIdString, object], camera_group: AniposeCameraGroup) -> dict[
    CameraIdString, object]:
    ordered_data_dict = {}

    for camera in camera_group.cameras:
        for camrea_id, data in data_by_camera.items():
            if camera.name in camrea_id:
                ordered_data_dict[camrea_id] = data
                break


    return ordered_data_dict
