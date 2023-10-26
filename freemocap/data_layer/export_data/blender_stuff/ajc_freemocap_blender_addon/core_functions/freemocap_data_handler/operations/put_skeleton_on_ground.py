import logging
from typing import Dict

import numpy as np

from ajc_freemocap_blender_addon.core_functions.freemocap_data_handler.handler import \
    FreemocapDataHandler
from ajc_freemocap_blender_addon.core_functions.freemocap_data_handler.operations.estimate_good_frame import \
    estimate_good_frame

logger = logging.getLogger(__name__)


def put_skeleton_on_ground(handler: FreemocapDataHandler):
    logger.info(
        f"Putting freemocap data in inertial reference frame...")

    ground_reference_trajectories_with_error = handler.get_trajectories(
        trajectory_names=["right_heel", "left_heel", "right_foot_index", "left_foot_index"],
        with_error=True)

    good_frame = estimate_good_frame(trajectories_with_error=ground_reference_trajectories_with_error)

    original_reference_trajectories = {trajectory_name: trajectory["trajectory"][good_frame, :]
                                       for trajectory_name, trajectory in
                                       ground_reference_trajectories_with_error.items()}

    center_reference_point = np.nanmean(list(original_reference_trajectories.values()), axis=0)

    x_forward_reference_points = []
    for trajectory in handler.get_trajectories(
            trajectory_names=["left_foot_index", "right_foot_index"]).values():
        x_forward_reference_points.append(trajectory[good_frame, :])
    x_forward_reference_point = np.nanmean(x_forward_reference_points, axis=0)

    y_leftward_reference_points = []
    for trajectory in handler.get_trajectories(
            trajectory_names=["left_heel", "left_foot_index"]).values():
        y_leftward_reference_points.append(trajectory[good_frame, :])
    y_leftward_reference_point = np.nanmean(y_leftward_reference_points, axis=0)

    z_upward_reference_point = handler.get_trajectory("head_center")[good_frame, :]
    
    x_forward = center_reference_point - y_leftward_reference_point
    y_left = x_forward_reference_point - center_reference_point
    z_up = z_upward_reference_point - center_reference_point

    # Make them orthogonal
    z_hat = np.cross(x_forward, y_left)
    y_hat = np.cross(x_forward, z_hat)
    x_hat = np.cross(y_hat, z_hat)

    # Normalize them
    x_hat = x_hat / np.linalg.norm(x_hat)
    y_hat = y_hat / np.linalg.norm(y_hat)
    z_hat = z_hat / np.linalg.norm(z_hat)

    rotation_matrix = np.array([x_hat, y_hat, z_hat])

    assert np.allclose(np.linalg.norm(x_hat), 1), "x_hat is not normalized"
    assert np.allclose(np.linalg.norm(y_hat), 1), "y_hat is not normalized"
    assert np.allclose(np.linalg.norm(z_hat), 1), "z_hat is not normalized"
    assert np.allclose(np.dot(z_hat, y_hat), 0), "z_hat is not orthogonal to y_hat"
    assert np.allclose(np.dot(z_hat, x_hat), 0), "z_hat is not orthogonal to x_hat"
    assert np.allclose(np.dot(y_hat, x_hat), 0), "y_hat is not orthogonal to x_hat"
    assert np.allclose(np.cross(x_hat, y_hat), z_hat), "Vectors do not follow right-hand rule"
    assert np.allclose(rotation_matrix @ x_hat, [1, 0, 0]), "x_hat is not rotated to [1, 0, 0]"
    assert np.allclose(rotation_matrix @ y_hat, [0, 1, 0]), "y_hat is not rotated to [0, 1, 0]"
    assert np.allclose(rotation_matrix @ z_hat, [0, 0, 1]), "z_hat is not rotated to [0, 0, 1]"
    assert np.allclose(np.linalg.det(rotation_matrix), 1), "rotation matrix is not a rotation matrix"

    handler.translate(translation=-center_reference_point)
    handler.mark_processing_stage("translated_to_origin",
                                  metadata={
                                      "original_origin_reference": center_reference_point.tolist()})
    handler.rotate(rotation=rotation_matrix)
    handler.mark_processing_stage(name="rotated_to_inertial_reference_frame",
                                  metadata={"rotation_matrix": rotation_matrix.tolist()})

    logger.success(
        "Finished putting freemocap data in inertial reference frame.\n freemocap_data(after):\n{handler}")


def get_body_trajectories_closest_to_the_ground(handler: FreemocapDataHandler) -> Dict[str, np.ndarray]:
    body_names = handler.body_names

    # checking for markers from the ground up!
    body_parts_from_low_to_high = [
        ("feet", ["right_heel", "left_heel", "right_foot_index", "left_foot_index"]),
        ("ankle", ["right_ankle", "left_ankle"]),
        ("knee", ["right_knee", "left_knee"]),
        ("hip", ["right_hip", "left_hip"]),
        ("shoulder", ["right_shoulder", "left_shoulder"]),
        ("head", ["nose", "right_eye_inner", "right_eye",
                  "right_eye_outer", "left_eye_inner",
                  "left_eye", "left_eye_outer",
                  "right_ear", "left_ear",
                  "mouth_right", "mouth_left"]),
    ]

    for part_name, part_list in body_parts_from_low_to_high:
        if all([part in body_names for part in part_list]):
            logger.debug(f"Trying to use {part_name} trajectories to define ground plane.")
            part_trajectories = handler.get_trajectories(part_list)

            for trajectory_name, trajectory in part_trajectories.items():
                if np.isnan(trajectory).all():
                    logger.warning(
                        f"Trajectory {trajectory_name} is all nan. Removing from lowest body trajectories.")
                    del part_trajectories[trajectory_name]

            if len(part_trajectories) < 2:
                logger.debug(f"Found less than 2 {part_name} trajectories. Trying next part..")
            else:
                logger.info(f"Found {part_name} trajectories. Using {part_name} as lowest body trajectories.")
                return part_trajectories

    logger.error(f"Found less than 2 head trajectories. Cannot find lowest body trajectories!")
    raise Exception("Cannot find lowest body trajectories!")
