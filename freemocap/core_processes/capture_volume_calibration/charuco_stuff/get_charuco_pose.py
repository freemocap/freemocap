import logging
from pathlib import Path
from typing import Tuple, Union
import cv2
import numpy as np
import toml

from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.get_anipose_calibration_object import (
    load_calibration_as_dict,
)
from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import (
    CharucoBoardDefinition,
)

logger = logging.getLogger(__name__)


def get_pose_vectors_from_charuco(
    image: np.ndarray,
    charuco_board_definition: CharucoBoardDefinition,
    camera_matrix: np.ndarray,
    distortion_coefficients: np.ndarray,
    display_image: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    charuco_board = charuco_board_definition.charuco_board
    charuco_detector = cv2.aruco.CharucoDetector(charuco_board)

    image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    charuco_corners, charuco_ids, marker_corners, marker_ids = charuco_detector.detectBoard(image_gray)
    if not (marker_ids is None) and len(marker_ids) > 0:
        cv2.aruco.drawDetectedMarkers(image, marker_corners)
    if not (charuco_ids is None) and len(charuco_ids) >= 4:
        cv2.aruco.drawDetectedCornersCharuco(image, charuco_corners, charuco_ids)
        try:
            obj_points, img_points = charuco_board.matchImagePoints(charuco_corners, charuco_ids)
            ret, rvec, tvec = cv2.solvePnP(obj_points, img_points, camera_matrix, distortion_coefficients)
            if ret:
                cv2.drawFrameAxes(image, camera_matrix, distortion_coefficients, rvec, tvec, 5)
        except cv2.error as error_inst:
            logger.error(error_inst.err)
    if display_image:
        try:
            cv2.imshow("image", image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        except cv2.error:
            logger.warning("Couldn't display image")

    return (rvec, tvec)


def get_camera_matrix_and_distortions_from_toml(
    calibration_toml_path: Union[str, Path],
    camera_name: str,
) -> Tuple[np.ndarray, np.ndarray]:
    calibration_dict = load_calibration_as_dict(calibration_toml_file_path=calibration_toml_path)
    camera_matrix = np.asarray(calibration_dict[camera_name]["matrix"])
    distortion_coefficients = np.asarray(calibration_dict[camera_name]["distortions"])

    return (camera_matrix, distortion_coefficients)


def get_camera_transformation_vectors_from_toml(
    calibration_toml_path: Union[str, Path],
    camera_name: str,
) -> Tuple[np.ndarray, np.ndarray]:
    calibration_dict = load_calibration_as_dict(calibration_toml_file_path=calibration_toml_path)
    rotation_vector = np.asarray(calibration_dict[camera_name]["rotation"])
    translation_vector = np.asarray(calibration_dict[camera_name]["translation"])

    return (rotation_vector, translation_vector)


def add_groundplane_vectors_to_calibration_toml(
    calibration_toml_path: Union[str, Path],
    groundplane_rotation_vector: np.ndarray,
    groundplane_translation_vector: np.ndarray,
) -> None:
    calibration_dict = load_calibration_as_dict(calibration_toml_file_path=calibration_toml_path)
    calibration_dict["groundplane"] = {}
    calibration_dict["groundplane"]["rotation"] = groundplane_rotation_vector.tolist()
    calibration_dict["groundplane"]["translation"] = groundplane_translation_vector.tolist()

    logger.info("Adding groundplane vectors to calibration toml")
    with open(str(calibration_toml_path), "w") as f:
        toml.dump(calibration_dict, f)


def compose_transformation_vectors(
    charuco_to_camera_rvec: np.ndarray,
    charuco_to_camera_tvec: np.ndarray,
    camera_to_world_rvec: np.ndarray,
    camera_to_world_tvec: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    results_tuple = cv2.composeRT(
        rvec1=charuco_to_camera_rvec,
        tvec1=charuco_to_camera_tvec,
        rvec2=camera_to_world_rvec,
        tvec2=camera_to_world_tvec,
    )
    composed_rvec = results_tuple[0].flatten()
    composed_tvec = results_tuple[1].flatten()
    return (composed_rvec, composed_tvec)


def find_groundplane_vector(
    calibration_toml_path: Union[str, Path],
    camera_name: str,
    video_pathstring: Union[str, Path],
) -> np.ndarray:
    charuco_board_definition = CharucoBoardDefinition()

    camera_matrix, distortion_coefficients = get_camera_matrix_and_distortions_from_toml(
        calibration_toml_path=calibration_toml_path, camera_name=camera_name
    )

    video_cap = cv2.VideoCapture(str(video_pathstring))
    ret, image = video_cap.read()

    if not ret:
        raise RuntimeError("Couldn't load video")

    rotation_vector, translation_vector = get_pose_vectors_from_charuco(
        image=image,
        charuco_board_definition=charuco_board_definition,
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion_coefficients,
    )

    existing_camera_rotation_vector, existing_camera_translation_vector = get_camera_transformation_vectors_from_toml(
        calibration_toml_path=calibration_toml_path, camera_name=camera_name
    )

    combined_rotation_vector, combined_translation_vector = compose_transformation_vectors(
        charuco_to_camera_rvec=rotation_vector,
        charuco_to_camera_tvec=translation_vector,
        camera_to_world_rvec=existing_camera_rotation_vector,
        camera_to_world_tvec=existing_camera_translation_vector,
    )

    add_groundplane_vectors_to_calibration_toml(
        calibration_toml_path=calibration_toml_path,
        groundplane_rotation_vector=combined_rotation_vector,
        groundplane_translation_vector=combined_translation_vector,
    )

    return combined_rotation_vector
