from dataclasses import dataclass
import time
import cv2
import numpy as np
from rich import print

from src.core_processor.board_detection.board_detection import BoardDetection, CharucoFramePayload
from src.core_processor.board_detection.charuco_constants import charuco_board_object

number_of_distortion_coefficients = 5  # may be 4, 5, 8, or 12, not sure of the trade-off there

@dataclass
class SingleCameraCalibrationData:
    reprojection_error: float = 1e9
    camera_matrix: np.ndarray = None
    lens_distortion_coefficients: np.ndarray = np.zeros((number_of_distortion_coefficients, 1))
    rotation_vectors_of_the_board: np.ndarray = None
    translation_vectors_of_the_board: np.ndarray = None
    lens_distortion_std_dev: float = None
    camera_location_std_dev: float = None


class CameraCalibration:
    def __init__(self, board_detection: BoardDetection):
        self._bd = board_detection

        self._current_calibration = SingleCameraCalibrationData()
        self._start_time = time.time()
        self._all_charuco_corners_list = []
        self._all_charuco_ids_list = []


    def perform_calibration(self):
        self._bd.process(
            show_window=True,
            save_video=False,
            post_processed_frame_cb=self._calibration_work,
        )

    def _calibration_work(self, webcam_id: str, charuco_frame_payload: CharucoFramePayload):
        elapsed_time = (charuco_frame_payload.raw_frame_payload.timestamp / 1e9) - self._start_time
        print(
            f"found frame from camera {webcam_id} at timestamp {elapsed_time:.3f}")

        if not charuco_frame_payload.charuco_data.full_board_found:
            print(f'reprojection error - {self._current_calibration.reprojection_error:.3f}')
            print(f'lens distortion coefficients - {np.array_str(np.squeeze(self._current_calibration.lens_distortion_coefficients), precision=2)}')
            return charuco_frame_payload.annotated_frame_image

        charuco_data = charuco_frame_payload.charuco_data
        image_width, image_height, color_channels = charuco_frame_payload.raw_frame_payload.image.shape

        self._current_calibration = self.calibrate_camera(charuco_data.charuco_corners,
                                                   charuco_data.charuco_ids,
                                                   image_width,
                                                   image_height,
                                                   )
        print(f'camera matrix - \n{np.array_str(self._current_calibration.camera_matrix, precision=2)}')

        # create new camera matrix that will show full undistored image (with black pixels in spots with no data (only for debugging)
        new_camera_matrix, valid_ROI_lbwh = cv2.getOptimalNewCameraMatrix(self._current_calibration.camera_matrix,
                                                          self._current_calibration.lens_distortion_coefficients,
                                                          (image_width, image_height),
                                                          1,
                                                          centerPrincipalPoint=True
                                                          )

        # https://docs.opencv.org/4.5.5/d9/d0c/group__calib3d.html#ga69f2545a8b62a6b0fc2ee060dc30559d
        undistorted_image = cv2.undistort(charuco_frame_payload.annotated_frame_image,
                                          self._current_calibration.camera_matrix,
                                          self._current_calibration.lens_distortion_coefficients,
                                          None,
                                          new_camera_matrix)

        return undistorted_image


    def calibrate_camera(self, charuco_corners_list, charuco_ids_list, image_width, image_height):
        """
        adapted from - https://mecaruco2.readthedocs.io/en/latest/notebooks_rst/Aruco/sandbox/ludovic/aruco_calibration_rotation.html

        Calibrates the camera using the charuco data

        helpful resources -
        https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html#ga3207604e4b1a1758aa66acb6ed5aa65d <-opencv's 3d camera calibration docs
        https://www.adamsmith.haus/python/docs/cv2.aruco.calibrateCameraCharucoExtended
        https://www.mathworks.com/help/vision/ug/camera-calibration.html
        https://docs.opencv.org/3.4/d9/db7/tutorial_py_table_of_contents_calib3d.html
        https://calib.io/blogs/knowledge-base/camera-models <-a good one
        """
        print("CAMERA CALIBRATION")

        if self._current_calibration.camera_matrix is None:
            self._current_calibration.camera_matrix = np.array([[float(image_width), 0., image_width / 2.],
                                                    [0., float(image_width), image_height / 2.],
                                                    [0., 0., 1.]])



        # flag definitions -> https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html#ga3207604e4b1a1758aa66acb6ed5aa65d
        flags = (cv2.CALIB_USE_INTRINSIC_GUESS + cv2.CALIB_FIX_ASPECT_RATIO + cv2.CALIB_FIX_PRINCIPAL_POINT + cv2.CALIB_TILTED_MODEL)
        # flags = (cv2.CALIB_RATIONAL_MODEL)

        # https://docs.opencv.org/4.x/d9/d6a/group__aruco.html#gacf03e5afb0bc516b73028cf209984a06
        (reprojection_error,
         camera_matrix,
         lens_distortion_coefficients,
         rotation_vectors_of_the_board,
         translation_vectors_of_the_board,
         lens_distortion_std_dev,
         camera_location_std_dev,
         reprojection_error_per_view
         ) = cv2.aruco.calibrateCameraCharucoExtended(
            charucoCorners=charuco_corners_list,
            charucoIds=charuco_ids_list,
            board=charuco_board_object,
            imageSize=(image_width, image_height),
            cameraMatrix=self._current_calibration.camera_matrix.copy(),
            distCoeffs=self._current_calibration.lens_distortion_coefficients.copy(),
            flags=flags,
            criteria=(cv2.TERM_CRITERIA_EPS & cv2.TERM_CRITERIA_COUNT, 10000, 1e-9))

        if reprojection_error > self._current_calibration.reprojection_error:
            return self._current_calibration

        return SingleCameraCalibrationData(
            reprojection_error=reprojection_error,
            camera_matrix=camera_matrix,
            lens_distortion_coefficients=lens_distortion_coefficients,
            rotation_vectors_of_the_board=rotation_vectors_of_the_board,
            translation_vectors_of_the_board=translation_vectors_of_the_board,
            lens_distortion_std_dev=lens_distortion_std_dev,
            camera_location_std_dev=camera_location_std_dev)



if __name__ == "__main__":
    print('start main')
    a = BoardDetection()
    b = CameraCalibration(a)
    b.perform_calibration()
