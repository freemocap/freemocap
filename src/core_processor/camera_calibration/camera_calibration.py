import logging
import traceback
from dataclasses import dataclass
import time
from pathlib import Path
from typing import Callable

import cv2
import matplotlib.pyplot as plt
import pyqtgraph as pg
import numpy as np
from rich import print

from src.cameras.multicam_manager.cv_camera_manager import CVCameraManager
from src.cameras.persistence.video_writer.save_options import SaveOptions
from src.core_processor.board_detection.board_detection import BoardDetection, CharucoFramePayload
from src.core_processor.board_detection.charuco_constants import charuco_board_object
from src.core_processor.board_detection.detect_charuco_board import CharucoViewData
from src.core_processor.camera_calibration.calibration_diagnostics_visualizer import CalibrationDiagnosticsVisualizer
from src.core_processor.fps.fps_counter import FPSCamCounter
from src.core_processor.show_cam_window import show_cam_window

logger = logging.getLogger(__name__)

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
    def __init__(self,
                 board_detection: BoardDetection = BoardDetection(),
                 cam_manager: CVCameraManager = CVCameraManager(),
                 show_calibration_diagnostics_visualizer=True, ):
        self._board_detection_object = board_detection
        self._cam_manager = cam_manager
        self._current_calibration = SingleCameraCalibrationData()
        self._start_time = time.time()
        self._all_charuco_views = []
        self._num_charuco_views = 0
        self._best_combo_of_charuco_views = []
        self._previous_best_calibrations = []
        self.show_calibration_diagnostics_visualizer = show_calibration_diagnostics_visualizer
        if self.show_calibration_diagnostics_visualizer:
            self.calibration_diagnostics_visualizer = CalibrationDiagnosticsVisualizer()


    async def process_by_cam_id(self, webcam_id: str, cb):
        with self._cam_manager.start_capture_session_single_cam(
                webcam_id=webcam_id,
        ) as session_obj:
            fps_manager = FPSCamCounter(self._cam_manager.available_webcam_ids)
            fps_manager.start_all()
            cv_cam = session_obj.cv_cam
            writer = session_obj.writer
            try:
                while True:
                    if not cv_cam.is_capturing_frames:
                        return
                    charuco_frame_payload = self._board_detection_object.detect_charuco_board_in_camera_stream(cv_cam)
                    if cb and charuco_frame_payload.annotated_frame_image is not None:
                        writer.write(charuco_frame_payload.raw_frame_payload)
                        await cb(charuco_frame_payload.annotated_frame_image)
            except Exception as e:
                logger.error("Printing traceback")
                traceback.print_exc()
                raise e
            finally:
                writer = session_obj.writer
                options = SaveOptions(
                    writer_dir=Path().joinpath(
                        cv_cam.session_writer_base_path,
                        "board_detection",
                        f"webcam_{cv_cam.webcam_id_as_str}",
                    ),
                    fps=fps_manager.current_fps_for(cv_cam.webcam_id_as_str),
                    frame_width=cv_cam.get_frame_width(),
                    frame_height=cv_cam.get_frame_height(),
                )
                writer.save(options)


    def perform_calibration(self):
        self.process(
            show_window=True,
            save_video=False,
            post_processed_frame_cb=self._calibration_work,
        )

    def process(
            self,
            post_processed_frame_cb: Callable[[str, CharucoFramePayload], None] = None,
            show_window=True,
            save_video=True,
    ):
        """
        Opens Cameras using OpenCV and begins image processing for charuco board
        If return images is true, the images are returned to the caller
        """
        # if its already capturing frames, this is a no-op

        with self._cam_manager.start_capture_session_all_cams() as session_obj:
            fps_manager = FPSCamCounter(self._cam_manager.available_webcam_ids)
            fps_manager.start_all()
            try:
                should_continue = True
                while should_continue:
                    for response in session_obj:
                        cv_cam = response.cv_cam
                        writer = response.writer
                        charuco_frame_payload = self._board_detection_object.detect_charuco_board_in_camera_stream(cv_cam)
                        current_webcam_id = cv_cam.webcam_id_as_str

                        if not charuco_frame_payload:
                            continue

                        if save_video:
                            writer.write(charuco_frame_payload.raw_frame_payload)

                        if post_processed_frame_cb:
                            undistorted_annotated_image = post_processed_frame_cb(current_webcam_id,
                                                                                  charuco_frame_payload)
                            charuco_frame_payload.annotated_frame_image = undistorted_annotated_image

                        fps_manager.increment_frame_processed_for(current_webcam_id)
                        if show_window:
                            should_continue = show_cam_window(
                                current_webcam_id, charuco_frame_payload.annotated_frame_image, fps_manager
                            )
            except:
                logger.error("Printing traceback")
                traceback.print_exc()
            finally:
                for response in session_obj:
                    cv_cam = response.cv_cam
                    writer = response.writer
                    options = SaveOptions(
                        writer_dir=Path().joinpath(
                            cv_cam.session_writer_base_path,
                            "board_detection",
                            f"webcam_{cv_cam.webcam_id_as_str}",
                        ),
                        fps=fps_manager.current_fps_for(cv_cam.webcam_id_as_str),
                        frame_width=cv_cam.get_frame_width(),
                        frame_height=cv_cam.get_frame_height(),
                    )
                    writer.save(options)
                    logger.info(f"Destroy window {cv_cam.webcam_id_as_str}")
                    cv2.destroyWindow(cv_cam.webcam_id_as_str)
                    cv2.waitKey(1)

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
        if self.show_calibration_diagnostics_visualizer:
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

        default_calibration = self.get_default_calibration(new_charuco_view,
                                                           number_of_distortion_coefficients=5)

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
                    cameraMatrix=default_calibration.camera_matrix,
                    distCoeffs=default_calibration.lens_distortion_coefficients,
                    flags=flags,
                    criteria=(cv2.TERM_CRITERIA_EPS & cv2.TERM_CRITERIA_COUNT, 10000, 1e-9))

                if self.show_calibration_diagnostics_visualizer:
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
                        self._previous_best_calibrations.append(self._current_calibration)

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

        # add default calibration (i.e. option not to change anything)
        # list_of_combos_of_charuco_views.append([self.get_default_calibration(new_charuco_view)])

        # add previous best view
        if self._best_combo_of_charuco_views:
            list_of_combos_of_charuco_views.append(self._best_combo_of_charuco_views.copy())

        # add previous best view + new view
        best_combo_plus_new = self._best_combo_of_charuco_views.copy()
        best_combo_plus_new.append(new_charuco_view)
        list_of_combos_of_charuco_views.append(best_combo_plus_new)

        # add all previous best calibrations
        # list_of_combos_of_charuco_views.append([cc for cc in self._previous_best_calibrations])

        # and a some random combos - half with the new view and half without it
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

        if self.check_if_too_many_invalid_pixels(this_calibration):
            return False

        return True

    def lens_distortion_is_monotonic(self, this_calibration, assume_wide_angle_lens=True) -> bool:
        """
        check if the lens distortion coefficients are valid by checking it the resulting undistorted image is monotonically increasing along each diagonal (i.e. the image doesn't wrap around itself)

        per opencv calib3d docs, calibrations are valid if -

        1 + k1*r^2 + k2*r^r + k3*r6

        is monotonically increasing (pincushion distortion) or monotonically decreasing (barrel distortion).

        non-monotonic behavior means the calibration is invalid, so we check for that by examining the `np.diff` of a vector of points extending from image center to the top left coners to make sure it never goes negative(NOTE - check other directions?)

        since most cameras are wide-angle (i.e. they give a wider field of view than a pinhole camera), we may constrain things further be requiring things be monotonically increasing (i.e. only return pincushion distortions to correct for the barrel distortion of a wide-angle field of view)


        see -
        https://www.mathworks.com/help/vision/ug/camera-calibration.html <- matlab docs (best ones, maybe)
        https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html <-mathematical defintion of lens distortion
        https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html#ga3207604e4b1a1758aa66acb6ed5aa65d <- docs explaining lens_distortion_coefficients
        https://github.com/opencv/opencv/issues/15992 <-conversation about the fact that opencv doesn't check for this kinda thing

        """
        calibration_valid = False

        # following naming conventions of open cv docs
        k1 = this_calibration.lens_distortion_coefficients[0]
        k2 = this_calibration.lens_distortion_coefficients[1]
        p1 = this_calibration.lens_distortion_coefficients[2]  # I think p1 and p2 are for tangential distortion...
        p2 = this_calibration.lens_distortion_coefficients[
            3]  # ...which I might want to check on later? Currently fixed at Zero
        k3 = this_calibration.lens_distortion_coefficients[4]

        number_of_points = 100
        original_points_x = np.linspace(-this_calibration.image_width, this_calibration.image_width, number_of_points)
        original_points_y = np.linspace(-this_calibration.image_height, this_calibration.image_height, number_of_points)

        original_points_xy = np.vstack((original_points_x, original_points_y))

        distorted_points_xy = cv2.undistortPoints(original_points_xy,
                                                  this_calibration.camera_matrix,
                                                  this_calibration.lens_distortion_coefficients)
        distorted_points_x = np.squeeze(distorted_points_xy[0])
        distorted_points_y = np.squeeze(distorted_points_xy[1])

        if self.show_calibration_diagnostics_visualizer:
            self.calibration_diagnostics_visualizer.update_image_point_remapping_subplot(original_points_x,
                                                                                     original_points_y,
                                                                                     distorted_points_x,
                                                                                     distorted_points_y)
        return True


    def check_if_too_many_invalid_pixels(self, this_calibration, how_many_is_too_many=.1) -> bool:
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

    @staticmethod
    def get_default_calibration(charuco_view: CharucoViewData, number_of_distortion_coefficients=4):
        image_width = charuco_view.image_width
        image_height = charuco_view.image_height

        initial_camera_matrix = np.array([[float(image_width), 0., image_width / 2.],
                                          [0., float(image_width), image_height / 2.],
                                          [0., 0., 1.]])
        initial_lens_distortion_coefficients = np.zeros((number_of_distortion_coefficients, 1))

        return SingleCameraCalibrationData(
            camera_matrix=initial_camera_matrix,
            lens_distortion_coefficients=initial_lens_distortion_coefficients,
            image_width=image_width,
            image_height=image_height,
        )


if __name__ == "__main__":
    print('start main')

    a = CameraCalibration()
    a.perform_calibration()
    if a.show_calibration_diagnostics_visualizer:
        a.calibration_diagnostics_visualizer.close()
