import logging
from typing import Dict, List

import cv2
import numpy as np

from src.cameras.capture.dataclasses.frame_payload import FramePayload
from src.pipelines.calibration_pipeline.charuco_board_detection.dataclasses.charuco_board_definition import (
    CharucoBoardDataClass,
)
from src.pipelines.calibration_pipeline.charuco_board_detection.dataclasses.charuco_frame_payload import (
    CharucoFramePayload,
)
from src.pipelines.calibration_pipeline.charuco_board_detection.dataclasses.charuco_view_data import (
    CharucoViewData,
)

from src.pipelines.calibration_pipeline.charuco_board_detection.charuco_image_annotator import (
    annotate_image_with_charuco_data,
)

logger = logging.getLogger(__name__)


class CharucoBoardDetector:
    def __init__(self):
        self.charuco_board_data_class_object = CharucoBoardDataClass()
        self.cv2_aruco_charuco_board = (
            self.charuco_board_data_class_object.charuco_board
        )
        self.aruco_marker_dict = self.charuco_board_data_class_object.aruco_marker_dict
        self.number_of_charuco_corners = (
            self.charuco_board_data_class_object.number_of_charuco_corners
        )

    def detect_charuco_board_in_frame_payload(
        self, raw_frame_payload: FramePayload
    ) -> CharucoFramePayload:

        if raw_frame_payload.image is None:
            logger.error("Frame is empty")
            return CharucoFramePayload()

        charuco_view_data = self.detect_charuco_board_in_an_image(
            raw_frame_payload.image
        )

        annotated_image = raw_frame_payload.image.copy()
        if charuco_view_data.some_charuco_corners_found:
            annotate_image_with_charuco_data(
                annotated_image,  # this image will have stuff drawn on top of it inside this function
                charuco_view_data,
                self.number_of_charuco_corners,
            )

        return CharucoFramePayload(
            annotated_image=annotated_image,
            raw_frame_payload=raw_frame_payload,
            charuco_view_data=charuco_view_data,
        )

    def detect_charuco_board_in_an_image(self, raw_image) -> CharucoViewData:
        """
        detect charuco board in an image.
        more-or-less copied from - https://mecaruco2.readthedocs.io/en/latest/notebooks_rst/Aruco/sandbox/ludovic/aruco_calibration_rotation.html

        """
        if raw_image is None:
            logger.error("Image is empty!")
            return CharucoViewData()

        image_height, image_width, num_color_channels = raw_image.shape
        charuco_corners = []
        charuco_ids = []

        # SUB PIXEL CORNER DETECTION CRITERION
        termination_criteria_threshold = (
            cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
            100,
            0.0001,
        )

        grayscale_image = cv2.cvtColor(raw_image, cv2.COLOR_BGR2GRAY)

        (
            aruco_square_corners,
            aruco_square_ids,
            rejected_image_points,
        ) = cv2.aruco.detectMarkers(grayscale_image, self.aruco_marker_dict)

        full_board_found = False
        any_markers_found = False
        some_charuco_corners_found = False

        if len(aruco_square_corners) > 0:
            any_markers_found = True
            # refine detected corner locations to provide sub-pixel precision
            # https://docs.opencv.org/4.x/dd/d1a/group__imgproc__feature.html#ga354e0d7c86d0d9da75de9b9701a9a87e
            for this_corner in aruco_square_corners:
                cv2.cornerSubPix(
                    grayscale_image,
                    this_corner,
                    winSize=(3, 3),
                    zeroZone=(-1, -1),
                    criteria=termination_criteria_threshold,
                )
            results = cv2.aruco.interpolateCornersCharuco(
                aruco_square_corners,
                aruco_square_ids,
                grayscale_image,
                self.cv2_aruco_charuco_board,
            )

            if (
                results[1] is not None
                and results[2] is not None
                and len(results[1]) > 3
            ):
                some_charuco_corners_found = True

                charuco_corners = results[1]
                charuco_ids = results[2]

                if len(charuco_ids) == self.number_of_charuco_corners:
                    full_board_found = True

        return CharucoViewData(
            charuco_board_object=self.charuco_board_data_class_object,
            full_board_found=full_board_found,
            some_charuco_corners_found=some_charuco_corners_found,
            any_markers_found=any_markers_found,
            charuco_corners=charuco_corners,
            charuco_ids=charuco_ids,
            aruco_square_corners=aruco_square_corners,
            aruco_square_ids=aruco_square_ids,
            image_width=image_width,
            image_height=image_height,
        )

    def format_charuco2d_data(self, this_multi_frame_charuco_data_list: List) -> Dict:

        number_of_tracked_points = this_multi_frame_charuco_data_list[
            0
        ].charuco_view_data.charuco_board_object.number_of_charuco_corners

        charuco2d_data_per_cam_dict = {}
        base_charuco_data_npy_with_nans_for_missing_data_xy = np.zeros(
            (number_of_tracked_points, 2)
        )
        base_charuco_data_npy_with_nans_for_missing_data_xy[:] = np.nan
        for this_cam_data in this_multi_frame_charuco_data_list:
            if this_cam_data.charuco_view_data.some_charuco_corners_found:
                this_frame_charuco_data_xy = (
                    base_charuco_data_npy_with_nans_for_missing_data_xy.copy()
                )
                charuco_ids_in_this_frame_idx = (
                    this_cam_data.charuco_view_data.charuco_ids
                )
                charuco_corners_in_this_frame_xy = (
                    this_cam_data.charuco_view_data.charuco_corners
                )
                this_frame_charuco_data_xy[
                    charuco_ids_in_this_frame_idx, :
                ] = charuco_corners_in_this_frame_xy

            this_webcam_id = this_cam_data.raw_frame_payload.webcam_id
            charuco2d_data_per_cam_dict[this_webcam_id] = this_frame_charuco_data_xy

        return charuco2d_data_per_cam_dict


if __name__ == "__main__":
    pass
    # ## Jon, Run me to easily start a charuco board detect run
    # print('starting icis_conference_main')
    # BoardDetection().process()
