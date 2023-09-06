from pathlib import Path
from typing import Dict
import cv2
import numpy as np

from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import (
    CharucoBoardDefinition,
)


def get_rotation_vector_from_charuco(
    image: np.ndarray,
    charuco_board_definition: CharucoBoardDefinition,
    camera_matrix: np.ndarray,
    distortion_coefficients: np.ndarray,
) -> np.ndarray:
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
            print(
                "SolvePnP recognize calibration pattern as non-planar pattern. To process this need to use "
                "minimum 6 points. The planar pattern may be mistaken for non-planar if the pattern is "
                "deformed or incorrect camera parameters are used."
            )
            print(error_inst.err)

    try:
        cv2.imshow("image", image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    except:
        print("couldn't display image")

    return rvec


def create_vector(point1, point2):
    """Put two points in, make a vector"""
    vector = point2 - point1
    return vector


def create_unit_vector(vector):
    """Take in a vector, make it a unit vector"""
    unit_vector = vector / np.linalg.norm(vector)
    return unit_vector


def calculate_skewed_symmetric_cross_product(cross_product_vector):
    skew_symmetric_cross_product = np.array(
        [
            [0, -cross_product_vector[2], cross_product_vector[1]],
            [cross_product_vector[2], 0, -cross_product_vector[0]],
            [-cross_product_vector[1], cross_product_vector[0], 0],
        ]
    )
    return skew_symmetric_cross_product


def calculate_rotation_matrix(vector1, vector2):
    """Put in two vectors to calculate the rotation matrix between those two vectors"""
    # based on the code found here: https://math.stackexchange.com/questions/180418/calculate-rotation-matrix-to-align-vector-a-to-vector-b-in-3d"""

    identity_matrix = np.identity(3)
    vector_cross_product = np.cross(vector1, vector2)
    vector_dot_product = np.dot(vector1, vector2)
    skew_symmetric_cross_product = calculate_skewed_symmetric_cross_product(vector_cross_product)
    rotation_matrix = (
        identity_matrix
        + skew_symmetric_cross_product
        + (np.dot(skew_symmetric_cross_product, skew_symmetric_cross_product))
        * (1 - vector_dot_product)
        / (np.linalg.norm(vector_cross_product) ** 2)
    )

    return rotation_matrix


def rotate_point(point, rotation_matrix):
    rotated_point = np.dot(rotation_matrix, point)
    return rotated_point


def rotate_skeleton_frame(this_frame_aligned_skeleton_data, rotation_matrix):
    """Take in a frame of skeleton data, and apply the rotation matrix to each point in the skeleton"""

    this_frame_rotated_skeleton = np.zeros(
        this_frame_aligned_skeleton_data.shape
    )  # initialize the array to hold the rotated skeleton data for this frame
    num_tracked_points = this_frame_aligned_skeleton_data.shape[0]

    for i in range(num_tracked_points):
        this_frame_rotated_skeleton[i, :] = rotate_point(this_frame_aligned_skeleton_data[i, :], rotation_matrix)

    return this_frame_rotated_skeleton


def create_rotation_matrix_from_rotation_vector(rotation_vector: np.ndarray) -> np.ndarray:
    origin_normal_unit_vector = create_vector(np.array([0, 0, 0]), np.array([0, 0, 1]))
    unit_rotation_vector = create_unit_vector(rotation_vector)
    return calculate_rotation_matrix(unit_rotation_vector, origin_normal_unit_vector)


def rotate_skeleton_data(skeleton_data: np.ndarray, rotation_matrix: np.ndarray) -> np.ndarray:
    rotated_skeleton_data = np.zeros(skeleton_data.shape)

    for frame in range(rotated_skeleton_data.shape[0]):  # rotate the skeleton on each frame
        rotated_skeleton_data[frame, :, :] = rotate_skeleton_frame(skeleton_data[frame, :, :], rotation_matrix)

    return rotated_skeleton_data

def compose_transformation_vectors(charuco_to_camera_rvec: np.ndarray, charuco_to_camera_tvec: np.ndarray, camera_to_world_rvec: np.ndarray, camera_to_world_tvec: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    #TODO: decide if this is worth a separate function for clarity - writing it down now to remember it.
    composed_rvec, composed_tvec = cv2.composeRT(
        rvec1=charuco_to_camera_rvec,
        tvec1=charuco_to_camera_tvec,
        rvec2=camera_to_world_rvec,
        tvec2=camera_to_world_tvec,
    )
    return composed_rvec, composed_tvec


if __name__ == "__main__":
    camera_matrix = np.array(
        [
            [1.53194096e03, 0.00000000e00, 1.01721388e03],
            [0.00000000e00, 1.54691324e03, 5.36380836e02],
            [0.00000000e00, 0.00000000e00, 1.00000000e00],
        ]
    )
    distortion_coefficients = np.array([[0.06806131, 0.03550422, 0.00044959, -0.00328774, -0.26919549]])
    image_pathstring = "/Users/philipqueen/Downloads/webcam_charuco_test_2.jpeg"

    # camera_matrix = np.array(
    #     [ [ 902.0875074058669, 0.0, 359.5,], [ 0.0, 902.0875074058669, 639.5,], [ 0.0, 0.0, 1.0,],]
    # )
    # distortion_coefficients = np.array(
    #     [ -0.29507044707574875, 0.0, 0.0, 0.0, 0.0,]
    # )
    # image_pathstring = "/Users/philipqueen/Downloads/sample_data_charuco_test_2.png"

    image = cv2.imread(image_pathstring)

    charuco_definition = CharucoBoardDefinition()

    rotation_matrix = get_rotation_vector_from_charuco(
        image=image,
        charuco_board_definition=charuco_definition,
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion_coefficients,
    )

    print(rotation_matrix)
