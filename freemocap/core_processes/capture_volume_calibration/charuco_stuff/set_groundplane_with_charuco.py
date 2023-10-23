import cv2
import numpy as np

from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import (
    CharucoBoardDefinition,
)
from freemocap.core_processes.capture_volume_calibration.charuco_stuff.get_charuco_pose import (
    get_camera_matrix_and_distortions_from_toml,
    get_camera_transformation_vectors_from_toml,
)


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
            print(
                "SolvePnP recognize calibration pattern as non-planar pattern. To process this need to use "
                "minimum 6 points. The planar pattern may be mistaken for non-planar if the pattern is "
                "deformed or incorrect camera parameters are used."
            )
            print(error_inst.err)
    if display_image:
        try:
            cv2.imshow("image", image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        except:
            print("Couldn't display image")

    return (rvec, tvec)


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
    print(vector1.shape)
    print(vector2.shape)
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


def rotate_skeleton_with_matrix(rotation_matrix: np.ndarray, original_skeleton_np_array: np.ndarray) -> np.ndarray:
    """
    Rotate the entire skeleton with given rotation matrix.

        Input:
            Rotation matrix: Rotation matrix describing the desired rotation
            Original skeleton data: The freemocap data you want to rotate
        Output:
            rotated_skeleton_data: A numpy data array of your rotated skeleton

    """
    rotated_skeleton_data_array = np.zeros(original_skeleton_np_array.shape)
    for frame in range(original_skeleton_np_array.shape[0]):
        rotated_skeleton_data_array[frame, :, :] = rotate_skeleton_frame(
            original_skeleton_np_array[frame, :, :], rotation_matrix
        )

    return rotated_skeleton_data_array


if __name__ == "__main__":
    camera_name = "cam_1"
    calibration_toml_path = "/Users/philipqueen/freemocap_data/recording_sessions/aaron_ground_charuco_test/recording_14_22_03_gmt-4_calibration/recording_14_22_03_gmt-4_calibration_camera_calibration.toml"

    camera_matrix, distortion_coefficients = get_camera_matrix_and_distortions_from_toml(
        calibration_toml_path=calibration_toml_path, camera_name=camera_name
    )

    video_pathstring = "/Users/philipqueen/freemocap_data/recording_sessions/aaron_ground_charuco_test/recording_14_23_11_gmt-4/synchronized_videos/Camera_000_synchronized.mp4"
    video_cap = cv2.VideoCapture(video_pathstring)
    ret, image = video_cap.read()

    charuco_definition = CharucoBoardDefinition()

    rotation_vector, translation_vector = get_pose_vectors_from_charuco(
        image=image,
        charuco_board_definition=charuco_definition,
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion_coefficients,
        display_image=True,
    )

    image = cv2.drawFrameAxes(image, camera_matrix, distortion_coefficients, rotation_vector, translation_vector, 1)
    cv2.imshow("Image with world coordinate system", image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
    rvec_back, _ = cv2.Rodrigues(rotation_matrix)
    print("Original rotation vector: ", rotation_vector)
    print("Rotation vector after conversion back and forth: ", rvec_back)

    print(f"charuco to camera rotation_vector: {rotation_vector}")

    existing_camera_rotation_vector, existing_camera_translation_vector = get_camera_transformation_vectors_from_toml(
        calibration_toml_path=calibration_toml_path, camera_name=camera_name
    )

    combined_rotation_vector, combined_translation_vector = compose_transformation_vectors(
        charuco_to_camera_rvec=rotation_vector,
        charuco_to_camera_tvec=translation_vector,
        camera_to_world_rvec=existing_camera_rotation_vector,
        camera_to_world_tvec=existing_camera_translation_vector,
    )

    print(f"combined_rotation_vector: {combined_rotation_vector}")
    print(f"combined_translation_vector: {combined_translation_vector}")

    flattened_combined_rotation_vector = combined_rotation_vector.flatten()

    # from here on is skellyforge stuff
    # rotation_matrix = create_rotation_matrix_from_rotation_vector(flattened_combined_rotation_vector)

    # print(f"rotation_matrix: {rotation_matrix}")

    # raw_skeleton_datapath = "/Users/philipqueen/freemocap_data/recording_sessions/charuco_groundplane_test/recording_13_27_26_gmt-6/output_data/mediaPipeSkel_3d_body_hands_face.npy"
    # raw_skeleton_data = np.load(raw_skeleton_datapath)
    # print(f"raw_skeleton_data shape: {raw_skeleton_data.shape}")

    # rotated_skeleton_data = rotate_skeleton_with_matrix(
    #     rotation_matrix=rotation_matrix, original_skeleton_np_array=raw_skeleton_data
    # )
    # print(f"rotated_skeleton_data shape: {rotated_skeleton_data.shape}")

    # translated_rotated_skeleton_data = rotated_skeleton_data + combined_translation_vector
    # print(f"translated_rotated_skeleton_data shape: {translated_rotated_skeleton_data.shape}")

    # np.save("/Users/philipqueen/freemocap_data/recording_sessions/charuco_groundplane_test/recording_13_27_26_gmt-6/output_data/mediaPipeSkel_3d_body_hands_face_rotated.npy", rotated_skeleton_data)
