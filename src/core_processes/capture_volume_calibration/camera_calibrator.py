import logging

import cv2

from src.cameras.capture.dataclasses.frame_payload import FramePayload
from src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from src.core_processes.capture_volume_calibration.calibration_dataclasses import (
    CameraCalibrationData,
)
from src.pipelines.calibration_pipeline.charuco_board_detection.charuco_board_detector import (
    CharucoBoardDetector,
)
from src.pipelines.calibration_pipeline.charuco_board_detection.charuco_image_annotator import (
    annotate_image_with_charuco_data,
)
from src.pipelines.calibration_pipeline.charuco_board_detection.dataclasses.charuco_view_data import (
    CharucoViewData,
)

logger = logging.getLogger(__name__)


class CameraCalibrator:
    def __init__(
        self,
        charuco_board_detector: CharucoBoardDetector = CharucoBoardDetector(),
    ):
        self._current_calibration = None
        self._charuco_board_detector = charuco_board_detector

    @property
    def charuco_board_detector(self):
        return self._charuco_board_detector

    def calibrate(self, this_camera: OpenCVCamera):
        annotated_image = self._process_incoming_frame(this_camera.latest_frame)

        return annotated_image

    def _process_incoming_frame(self, raw_frame_payload: FramePayload):

        charuco_frame_payload = (
            self._charuco_board_detector.detect_charuco_board_in_frame_payload(
                raw_frame_payload
            )
        )

        charuco_view_data = charuco_frame_payload.charuco_view_data

        if self._current_calibration is None:
            self._current_calibration = CameraCalibrationData(
                charuco_view_data.image_width, charuco_view_data.image_height
            )

        if not charuco_view_data.full_board_found and self._current_calibration is None:
            return charuco_frame_payload.annotated_image, self._current_calibration

        if charuco_view_data.full_board_found:
            self._calibrate_camera(charuco_view_data)  # this is where the magic happens

        if charuco_view_data.some_charuco_corners_found:
            annotate_image_with_charuco_data(
                raw_frame_payload.image,  # this image will have stuff drawn on top of it inside this function
                charuco_view_data,
                self._charuco_board_detector.number_of_charuco_corners,
            )

        undistorted_image = cv2.undistort(
            raw_frame_payload.image,
            self._current_calibration.camera_matrix,
            self._current_calibration.lens_distortion_coefficients,
        )

        return undistorted_image, self._current_calibration

    def _calibrate_camera(self, charuco_view: CharucoViewData):
        """
        adapted from - https://mecaruco2.readthedocs.io/en/latest/notebooks_rst/Aruco/sandbox/ludovic/aruco_calibration_rotation.html

        Calibrates the camera using the charuco data

        helpful resources -
        https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html <-opencv's 3d camera calibration docs
        https://www.adamsmith.haus/python/docs/cv2.aruco.calibrateCameraCharucoExtended
        https://www.mathworks.com/help/vision/ug/camera-calibration.html
        https://docs.opencv.org/3.4/d9/db7/tutorial_py_table_of_contents_calib3d.html
        https://calib.io/blogs/knowledge-base/camera-models <-a good one
        """
        print("CAMERA CALIBRATION")

        image_width = charuco_view.image_width
        image_height = charuco_view.image_height

        # flag definitions -> https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html#ga3207604e4b1a1758aa66acb6ed5aa65d
        flags = (
            cv2.CALIB_USE_INTRINSIC_GUESS
            + cv2.CALIB_ZERO_TANGENT_DIST
            + cv2.cv2.CALIB_FIX_ASPECT_RATIO
            + cv2.CALIB_FIX_PRINCIPAL_POINT
            +
            # cv2.CALIB_FIX_FOCAL_LENGTH
            cv2.CALIB_RATIONAL_MODEL
            # cv2.CALIB_THIN_PRISM_MODEL
            # cv2.CALIB_TILTED_MODEL
        )

        # https://docs.opencv.org/4.x/d9/d6a/group__aruco.html#gacf03e5afb0bc516b73028cf209984a06
        (
            this_reprojection_error,
            this_camera_matrix,
            these_lens_distortion_coefficients,
            these_rotation_vectors_of_the_board,
            these_translation_vectors_of_the_board,
            this_lens_distortion_std_dev,
            this_camera_location_std_dev,
            these_reprojection_error_per_view,
        ) = cv2.aruco.calibrateCameraCharucoExtended(
            charucoCorners=[charuco_view.charuco_corners],
            charucoIds=[charuco_view.charuco_ids],
            board=self._charuco_board_detector.cv2_aruco_charuco_board,
            imageSize=(image_width, image_height),
            cameraMatrix=self._current_calibration.camera_matrix,
            distCoeffs=self._current_calibration.lens_distortion_coefficients,
            flags=flags,
            criteria=(cv2.TERM_CRITERIA_EPS & cv2.TERM_CRITERIA_COUNT, 10000, 1e-9),
        )

        if this_reprojection_error < self._current_calibration.reprojection_error:
            self._current_calibration = CameraCalibrationData(
                reprojection_error=this_reprojection_error,
                camera_matrix=this_camera_matrix,
                lens_distortion_coefficients=these_lens_distortion_coefficients,
                image_width=image_width,
                image_height=image_height,
                rotation_vectors_of_the_board=these_rotation_vectors_of_the_board,
                translation_vectors_of_the_board=these_translation_vectors_of_the_board,
                lens_distortion_std_dev=this_lens_distortion_std_dev,
                camera_location_std_dev=this_camera_location_std_dev,
            )

    def reconstruct_3d_charuco(self, charuco_data_per_camera_dictionary):
        pass
