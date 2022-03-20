from dataclasses import dataclass
import time
import cv2
import matplotlib.pyplot as plt
import pyqtgraph as pg
import numpy as np
from rich import print

from src.core_processor.board_detection.board_detection import BoardDetection, CharucoFramePayload
from src.core_processor.board_detection.charuco_constants import charuco_board_object
from src.core_processor.board_detection.detect_charuco_board import CharucoViewData
from src.core_processor.camera_calibration.calibration_diagnostics_visualizer import CalibrationDiagnosticsVisualizer


@dataclass
class SingleCameraCalibrationData:
    reprojection_error: float = None
    camera_matrix: np.ndarray = None
    lens_distortion_coefficients: np.ndarray = None
    image_width: int = None
    image_height: int = None
    rotation_vectors_of_the_board: np.ndarray = None
    translation_vectors_of_the_board: np.ndarray = None
    lens_distortion_std_dev: float = None
    camera_location_std_dev: float = None


class CameraCalibration:
    def __init__(self, board_detection: BoardDetection, visualize_calibration_disagnostics=True, ):
        self._bd = board_detection
        self._current_calibration = SingleCameraCalibrationData()
        self._start_time = time.time()
        self._all_charuco_views = []
        self._num_charuco_views = 0
        self._best_combo_of_charuco_views = []

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

        if not charuco_frame_payload.charuco_view_data.full_board_found and self._current_calibration.camera_matrix is None:
            return charuco_frame_payload.annotated_frame_image

        if charuco_frame_payload.charuco_view_data.full_board_found:
            new_charuco_view = charuco_frame_payload.charuco_view_data
            self._all_charuco_views.append(new_charuco_view)
            self._num_charuco_views = len(self._all_charuco_views)

            if self._num_charuco_views < 2:
                return charuco_frame_payload.annotated_frame_image

            self.estimate_lens_distortion(new_charuco_view)


        # raw_image = charuco_frame_payload.raw_frame_payload.image
        raw_image = charuco_frame_payload.annotated_frame_image

        if self._current_calibration.camera_matrix is None:
            return raw_image

        undistorted_image_for_debug = self.undistort_image_with_invalid_pixels_as_black(raw_image,
                                                                                        self._current_calibration)

        self.calibration_diagnostics_visualizer.update_image_subplot(undistorted_image_for_debug)

        undistorted_image = cv2.undistort(raw_image,
                                          self._current_calibration.camera_matrix,
                                          self._current_calibration.lens_distortion_coefficients,
                                          )

        print(
            f"found frame from camera {webcam_id} at timestamp {elapsed_time:.3f} - reprojection error: {self._current_calibration.reprojection_error:.3f} - num charuco views:{len(self._all_charuco_views)}")
        return undistorted_image

    def estimate_lens_distortion(self,
                                 new_charuco_view: CharucoViewData,
                                 max_iterations=10,
                                 max_charuco_board_views=5) -> SingleCameraCalibrationData:
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

        if not self._current_calibration.reprojection_error:
            current_best_reprojection_error = 1e9  # put a big fake number on the first frame
        else:
            current_best_reprojection_error = self._current_calibration.reprojection_error

        image_width = new_charuco_view.image_width
        image_height = new_charuco_view.image_height

        initial_camera_matrix = np.array([[float(image_width), 0., image_width / 2.],
                                          [0., float(image_width), image_height / 2.],
                                          [0., 0., 1.]])
        number_of_distortion_coefficients = 4  # may be 4, 5, 8, or 12, not sure of the trade-off there but low numbers seem more stable
        initial_lens_distortion_coefficients = np.zeros((number_of_distortion_coefficients, 1))

        num_charuco_views_per_combo = 10
        if self._num_charuco_views < num_charuco_views_per_combo:
            list_of_combos_of_charuco_views = [self._all_charuco_views]
        else:
            list_of_combos_of_charuco_views = self.generate_combos_of_charuco_views(new_charuco_view)

        # flag definitions -> https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html#ga3207604e4b1a1758aa66acb6ed5aa65d
        flags = (cv2.CALIB_USE_INTRINSIC_GUESS +
                 cv2.CALIB_ZERO_TANGENT_DIST +
                 cv2.cv2.CALIB_FIX_ASPECT_RATIO +
                 cv2.CALIB_FIX_PRINCIPAL_POINT +
                 cv2.CALIB_RATIONAL_MODEL
                 # cv2.CALIB_THIN_PRISM_MODEL
                 # cv2.CALIB_TILTED_MODEL
                 )

        for this_combo_of_charuco_views in list_of_combos_of_charuco_views:
            for this_charuco_view in this_combo_of_charuco_views:
                # https://docs.opencv.org/4.x/d9/d6a/group__aruco.html#gacf03e5afb0bc516b73028cf209984a06
                (this_reprojection_error,
                 this_camera_matrix,
                 these_lens_distortion_coefficients,
                 these_rotation_vectors_of_the_board,
                 these_translation_vectors_of_the_board,
                 this_lens_distortion_std_dev,
                 this_camera_location_std_dev,
                 these_reprojection_error_per_view
                 ) = cv2.aruco.calibrateCameraCharucoExtended(
                    charucoCorners=[this_charuco_view.charuco_corners],
                    charucoIds=[this_charuco_view.charuco_ids],
                    board=charuco_board_object,
                    imageSize=(image_width, image_height),
                    cameraMatrix=initial_camera_matrix,
                    distCoeffs=initial_lens_distortion_coefficients,
                    flags=flags,
                    criteria=(cv2.TERM_CRITERIA_EPS & cv2.TERM_CRITERIA_COUNT, 10000, 1e-9))

                self.calibration_diagnostics_visualizer.update_reprojection_error_subplot(this_reprojection_error,
                                                                                          current_best_reprojection_error)

                if this_reprojection_error < current_best_reprojection_error:

                    this_calibration = SingleCameraCalibrationData(
                        reprojection_error=this_reprojection_error,
                        camera_matrix=this_camera_matrix,
                        lens_distortion_coefficients=these_lens_distortion_coefficients,
                        image_width=image_width,
                        image_height=image_height,
                        rotation_vectors_of_the_board=these_rotation_vectors_of_the_board,
                        translation_vectors_of_the_board=these_translation_vectors_of_the_board,
                        lens_distortion_std_dev=this_lens_distortion_std_dev,
                        camera_location_std_dev=this_camera_location_std_dev)

                    if self.is_this_calibration_valid(this_calibration):
                        self._current_calibration = this_calibration

    def generate_combos_of_charuco_views(self,
                                         new_charuco_view,
                                         num_combos_to_generate=10,
                                         num_views_per_combo=5):
        """
        return -
        1x current best combo plus new view
        num_combos_to_generate/2x random combo WITH new view appended
        num_combos_to_generate/2x random combo WITHOUT new view appended
        """

        list_of_combos_of_charuco_views = []

        best_combo_plus_new = self._best_combo_of_charuco_views.copy()
        best_combo_plus_new.append(new_charuco_view)
        list_of_combos_of_charuco_views.append(best_combo_plus_new)

        for this_iter in range(num_combos_to_generate):
            this_random_sample_of_charuco_views = np.random.choice(num_views_per_combo,
                                                                   size=min(len(self._all_charuco_views),
                                                                            num_views_per_combo),
                                                                   replace=False)

            this_combo = [self._all_charuco_views[cc] for cc in this_random_sample_of_charuco_views]

            if this_iter < np.ceil(num_views_per_combo / 2):
                this_combo.append(new_charuco_view)

            list_of_combos_of_charuco_views.append(this_combo)

        return list_of_combos_of_charuco_views

    def is_this_calibration_valid(self, this_calibration):

        is_valid = False
        if not self.lens_distortion_is_monotonic(this_calibration):
            return False

        if self.too_many_invalid_pixels(this_calibration):
            return False

        return True

    def lens_distortion_is_monotonic(self, this_calibration) -> bool:
        """
        check if the lens distortion coefficients are valid by checking it the resulting undistorted image is monotonically increasing along each diagonal (i.e. the image doesn't wrap around itself)

        per opencv calib3d docs, calibrations are valid if -

        1 + k1*r^2 + k2*r^r + k3*r6

        is monotonically increasing (pincushion distortion) or monotonically decreasing (barrel distortion).

        non-monotonic behavior means the calibration is invalid, so we check for that by examining the `np.diff` of a vector of points extending from image center to the top left coners to make sure it never goes negative(NOTE - check other directions?)

        since most cameras are wide-angle (i.e. they give a wider field of view than a pinhole camera), we may constrain things further be requiring things be monotonically increasing (i.e. only return pincushion distortions)


        see -
        https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html <-mathematical defintion of lens distortion
        https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html#ga3207604e4b1a1758aa66acb6ed5aa65d <- docs explaining lens_distortion_coefficients
        https://github.com/opencv/opencv/issues/15992 <-conversation about the fact that opencv doesn't check for this kinda thing

        """
        calibration_valid = False

        pixel_distance_to_image_corner = np.sqrt(np.power(this_calibration.image_width, 2)
                                                 + np.power(this_calibration.image_height, 2))

        distances_from_image_center = np.linspace(-pixel_distance_to_image_corner,
                                                  pixel_distance_to_image_corner)  # aka,  the  `r` as defined in teh docs

        # following naming conventions
        k1 = this_calibration.lens_distortion_coefficients[0]
        k2 = this_calibration.lens_distortion_coefficients[1]
        p1 = this_calibration.lens_distortion_coefficients[2]  # I think p1 and p2 are for tangential distortion...
        p2 = this_calibration.lens_distortion_coefficients[3]  # ...which I might want to check on later?
        k3 = this_calibration.lens_distortion_coefficients[4]

        distorted_points = 1 + \
                           k1 * np.power(distances_from_image_center, 2) + \
                           k2 * np.power(distances_from_image_center, 4) + \
                           k3 * np.power(distances_from_image_center, 6)

        diff_distorted_points = np.diff(distances_from_image_center)

        # if show_debug_plot:
        #     fig = plt.Figure()
        #     fig.suptitle('is_calibration_valid - debug plot')
        #     plt.plot(distances_from_image_center, label='Distance from center of image')
        #     plt.plot(distorted_points, label='Distorted points')
        #     plt.legend(loc="upper left")
        #     plt.show()

        if np.sum(diff_distorted_points < 0) == 0:
            print(f'Yay! Monotonic! k1={k1}, k2={k2}, k3={k3}')
            return True

        print(f'Boo! Non-monotonic! k1={k1}, k2={k2}, k3={k3}')
        return False

    def too_many_invalid_pixels(self, this_calibration, how_many_is_too_many=.75) -> bool:
        """
        create new camera matrix that will show full undistored image with black pixels in spots with no data.
        return FALSE if black pixels are greater than `how_many_is_too_many` proportion of the full image
        """

        dummy_image = np.ones((this_calibration.image_width, this_calibration.image_height), np.uint8) * 255

        undistorted_image = self.undistort_image_with_invalid_pixels_as_black(dummy_image, this_calibration)

        num_invalid_pixels = np.sum(undistorted_image == 0)
        proportion_invalid_pixels = num_invalid_pixels / dummy_image.size

        if proportion_invalid_pixels > how_many_is_too_many:
            return True
        return False

    @staticmethod
    def undistort_image_with_invalid_pixels_as_black(image, calibration):
        new_camera_matrix, valid_ROI_lbwh = cv2.getOptimalNewCameraMatrix(
            calibration.camera_matrix,
            calibration.lens_distortion_coefficients,
            (calibration.image_width, calibration.image_height),
            1,
            centerPrincipalPoint=True
        )

        # https://docs.opencv.org/4.5.5/d9/d0c/group__calib3d.html#ga69f2545a8b62a6b0fc2ee060dc30559d
        undistorted_image = cv2.undistort(image,
                                          calibration.camera_matrix,
                                          calibration.lens_distortion_coefficients,
                                          None,
                                          new_camera_matrix)

        return undistorted_image


if __name__ == "__main__":
    print('start main')
    a = BoardDetection()
    b = CameraCalibration(a)
    b.perform_calibration()
    b.calibration_diagnostics_visualizer.close()
