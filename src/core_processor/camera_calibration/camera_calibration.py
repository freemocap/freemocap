from dataclasses import dataclass
import time
import cv2
import pyqtgraph as pg
import numpy as np
from rich import print

from src.core_processor.board_detection.board_detection import BoardDetection, CharucoFramePayload
from src.core_processor.board_detection.charuco_constants import charuco_board_object
from src.core_processor.camera_calibration.calibration_diagnostics_visualizer import CalibrationDiagnosticsVisualizer


@dataclass
class SingleCameraCalibrationData:
    reprojection_error: float = 1e9
    camera_matrix: np.ndarray = None
    lens_distortion_coefficients: np.ndarray = None
    rotation_vectors_of_the_board: np.ndarray = None
    translation_vectors_of_the_board: np.ndarray = None
    lens_distortion_std_dev: float = None
    camera_location_std_dev: float = None



class CameraCalibration:
    def __init__(self, board_detection: BoardDetection, visualize_calibration_disagnostics=True, ):
        self._bd = board_detection
        self._current_calibration = SingleCameraCalibrationData()
        self._start_time = time.time()
        self._all_charuco_corners_list = []
        self._all_charuco_ids_list = []

        if visualize_calibration_disagnostics:
            self.calibration_diagnostics_visualizer = CalibrationDiagnosticsVisualizer()

    def perform_calibration(self):
        self._bd.process(
            show_window=True,
            save_video=False,
            post_processed_frame_cb=self._calibration_work,
        )

    def _calibration_work(self, webcam_id: str, charuco_frame_payload: CharucoFramePayload):
        elapsed_time = (charuco_frame_payload.raw_frame_payload.timestamp / 1e9) - self._start_time

        image_width, image_height, color_channels = charuco_frame_payload.raw_frame_payload.image.shape

        if not charuco_frame_payload.charuco_data.full_board_found and self._current_calibration.camera_matrix is None:
            return charuco_frame_payload.annotated_frame_image

        if charuco_frame_payload.charuco_data.full_board_found:
            self._all_charuco_corners_list.append(charuco_frame_payload.charuco_data.charuco_corners)
            self._all_charuco_ids_list.append(charuco_frame_payload.charuco_data.charuco_ids)

            self.estimate_lens_distortion(image_width, image_height, )

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

        self.calibration_diagnostics_visualizer.update(self._current_calibration.reprojection_error)

        print(
            f"found frame from camera {webcam_id} at timestamp {elapsed_time:.3f} - reprojection error: {self._current_calibration.reprojection_error:.3f} - num charuco views:{len(self._all_charuco_corners_list)}")
        # print(f'lens distortion coefficients - {np.array_str(np.squeeze(self._current_calibration.lens_distortion_coefficients), precision=2)}')
        # print(f'camera matrix - \n{np.array_str(self._current_calibration.camera_matrix, precision=2)}')

        return undistorted_image

    def estimate_lens_distortion(self, image_width, image_height,
                                 max_iterations=5, max_charuco_board_views=10):
        """
        adapted from - https://mecaruco2.readthedocs.io/en/latest/notebooks_rst/Aruco/sandbox/ludovic/aruco_calibration_rotation.html

        Calibrates the camera using the charuco data using a RANSAC-like method - randomly selects board views and saves the combo that minimized reprojection error

        helpful resources -
        https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html <-opencv's 3d camera calibration docs
        https://www.adamsmith.haus/python/docs/cv2.aruco.calibrateCameraCharucoExtended
        https://www.mathworks.com/help/vision/ug/camera-calibration.html
        https://docs.opencv.org/3.4/d9/db7/tutorial_py_table_of_contents_calib3d.html
        https://calib.io/blogs/knowledge-base/camera-models <-a good one
        """
        print("CAMERA CALIBRATION")

        initial_camera_matrix = np.array([[float(image_width), 0., image_width / 2.],
                                          [0., float(image_width), image_height / 2.],
                                          [0., 0., 1.]])
        number_of_distortion_coefficients = 4  # may be 4, 5, 8, or 12, not sure of the trade-off there but low numbers seem more stable
        initial_lens_distortion_coefficients = np.zeros((number_of_distortion_coefficients, 1))

        num_charuco_views = len(self._all_charuco_ids_list)

        # flag definitions -> https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html#ga3207604e4b1a1758aa66acb6ed5aa65d
        flags = (cv2.CALIB_USE_INTRINSIC_GUESS +
                 # cv2.CALIB_ZERO_TANGENT_DIST +
                 cv2.cv2.CALIB_FIX_ASPECT_RATIO +
                 cv2.CALIB_FIX_PRINCIPAL_POINT +
                 cv2.CALIB_RATIONAL_MODEL
                 # cv2.CALIB_THIN_PRISM_MODEL
                 # cv2.CALIB_TILTED_MODEL
                 )
        # flags = (cv2.CALIB_RATIONAL_MODEL)

        for iter in range(max_iterations):

            if num_charuco_views < 2:
                these_charuco_corners = self._all_charuco_corners_list
                these_charuco_ids = self._all_charuco_ids_list
            else:
                this_random_sample_of_charuco_views = np.random.choice(num_charuco_views,
                                                                       size=min(num_charuco_views,
                                                                                max_charuco_board_views),
                                                                       replace=False)
                these_charuco_corners = [self._all_charuco_corners_list[cc] for cc in
                                         this_random_sample_of_charuco_views]
                these_charuco_ids = [self._all_charuco_ids_list[cc] for cc in this_random_sample_of_charuco_views]

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
                charucoCorners=these_charuco_corners,
                charucoIds=these_charuco_ids,
                board=charuco_board_object,
                imageSize=(image_width, image_height),
                cameraMatrix=initial_camera_matrix,
                distCoeffs=initial_lens_distortion_coefficients,
                flags=flags,
                criteria=(cv2.TERM_CRITERIA_EPS & cv2.TERM_CRITERIA_COUNT, 10000, 1e-9))

            if reprojection_error < self._current_calibration.reprojection_error:
                self._current_calibration = SingleCameraCalibrationData(reprojection_error=reprojection_error,
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
    b.calibration_diagnostics_visualizer.close()
