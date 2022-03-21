import logging
from dataclasses import dataclass

import cv2
import numpy as np

from src.cameras.capture.frame_payload import FramePayload
from src.core_processor.board_detection.charuco_constants import aruco_marker_dict, charuco_board_object, \
    number_of_charuco_corners
from src.core_processor.board_detection.detect_charuco_board import detect_charuco_board, CharucoViewData
from src.core_processor.board_detection.charuco_image_annotator import (
    annotate_image_with_charuco_data,
)

logger = logging.getLogger(__name__)


@dataclass
class CharucoFramePayload:
    raw_frame_payload: FramePayload
    annotated_frame_image: np.ndarray
    charuco_view_data: CharucoViewData


class BoardDetector:
    @staticmethod
    def detect_charuco_board_in_camera_stream(cv_cam) -> CharucoFramePayload:
        raw_frame_payload = cv_cam.latest_frame

        if not raw_frame_payload.success:
            # logger.error("CV2 failed to grab a frame")
            return
        if raw_frame_payload.image is None:
            logger.error("Frame is empty")
            return
        charuco_view_data = detect_charuco_board(raw_frame_payload.image)

        annotated_image = raw_frame_payload.image.copy()
        if charuco_view_data.some_charuco_corners_found:
            annotate_image_with_charuco_data(
                annotated_image,  # this image will have stuff drawn on top of it inside this function
                cv_cam.webcam_id_as_str,
                charuco_view_data
            )
            cv2.polylines(annotated_image, np.int32([charuco_view_data.charuco_corners]), True, (0, 100, 255), 2)

        return CharucoFramePayload(
            annotated_frame_image=annotated_image,
            raw_frame_payload=raw_frame_payload,
            charuco_view_data=charuco_view_data
        )

    @staticmethod
    def detect_charuco_board(image) -> CharucoViewData:
        """
        detect charuco board in an image.
        more-or-less copied from - https://mecaruco2.readthedocs.io/en/latest/notebooks_rst/Aruco/sandbox/ludovic/aruco_calibration_rotation.html

        """
        charuco_corners = []
        charuco_ids = []

        # SUB PIXEL CORNER DETECTION CRITERION
        termination_criteria_threshold = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.00001)

        grayscale_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        aruco_square_corners, aruco_square_ids, rejected_image_points = cv2.aruco.detectMarkers(
            grayscale_image, aruco_marker_dict
        )

        full_board_found = False
        any_markers_found = False
        some_charuco_corners_found = False

        if len(aruco_square_corners) > 0:
            any_markers_found = True
            # refine detected corner locations to provide sub-pixel precision
            # https://docs.opencv.org/4.x/dd/d1a/group__imgproc__feature.html#ga354e0d7c86d0d9da75de9b9701a9a87e
            for this_corner in aruco_square_corners:
                cv2.cornerSubPix(
                    grayscale_image, this_corner, winSize=(3, 3), zeroZone=(-1, -1),
                    criteria=termination_criteria_threshold
                )
            res2 = cv2.aruco.interpolateCornersCharuco(aruco_square_corners,
                                                       aruco_square_ids,
                                                       grayscale_image,
                                                       charuco_board_object
                                                       )

            if res2[1] is not None and res2[2] is not None and len(res2[1]) > 3:
                some_charuco_corners_found = True

                if len(res2[2]) == number_of_charuco_corners:
                    full_board_found = True

                charuco_corners = res2[1]
                charuco_ids = res2[2]

        return CharucoViewData(full_board_found=full_board_found,
                               some_charuco_corners_found=some_charuco_corners_found,
                               any_markers_found=any_markers_found,
                               charuco_corners=charuco_corners,
                               charuco_ids=charuco_ids,
                               aruco_square_corners=aruco_square_corners,
                               aruco_square_ids=aruco_square_ids)


if __name__ == "__main__":
    pass
    # ## Jon, Run me to easily start a charuco board detect run
    # print('starting main')
    # BoardDetection().process()
