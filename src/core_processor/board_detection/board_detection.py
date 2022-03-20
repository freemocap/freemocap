import logging
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from types import FunctionType
from typing import Any, Callable, Optional

import cv2
import numpy as np

from src.cameras.capture.frame_payload import FramePayload
from src.cameras.multicam_manager.cv_camera_manager import CVCameraManager
from src.cameras.persistence.video_writer.video_writer import SaveOptions
from src.core_processor.board_detection.charuco_constants import aruco_marker_dict, charuco_board_object, \
    number_of_charuco_corners
from src.core_processor.board_detection.detect_charuco_board import detect_charuco_board, CharucoViewData
from src.core_processor.board_detection.charuco_image_annotator import (
    annotate_image_with_charuco_data,
)
from src.core_processor.fps.fps_counter import FPSCamCounter
from src.core_processor.show_cam_window import show_cam_window
from src.core_processor.utils.image_fps_writer import write_fps_to_image

logger = logging.getLogger(__name__)

@dataclass
class CharucoFramePayload:
    raw_frame_payload: FramePayload
    annotated_frame_image: np.ndarray
    charuco_view_data: CharucoViewData

class BoardDetection:
    def __init__(self, cam_manager: CVCameraManager = CVCameraManager()):
        print('pre-henlo')
        self._cam_manager = cam_manager

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
                    charuco_frame_payload = self._detect_charuco_board_in_image(cv_cam)
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

    def process(
        self, post_processed_frame_cb:Callable[[str, CharucoFramePayload], None]=None, show_window=True, save_video=True,
    ):
        """
        Opens Camera using OpenCV and begins image processing for charuco board
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
                        charuco_frame_payload = self._detect_charuco_board_in_image(cv_cam)
                        current_webcam_id = cv_cam.webcam_id_as_str

                        if not charuco_frame_payload:
                            continue

                        if save_video:
                            writer.write(charuco_frame_payload.raw_frame_payload)

                        if post_processed_frame_cb:
                            undistorted_annotated_image = post_processed_frame_cb(current_webcam_id, charuco_frame_payload)
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

    def _detect_charuco_board_in_image(self, cv_cam):
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
                annotated_image, #this image will have stuff drawn on top of it inside this function
                cv_cam.webcam_id_as_str,
                charuco_view_data
            )
            cv2.polylines(annotated_image, np.int32([charuco_view_data.charuco_corners]), True, (0, 100, 255), 2)


        return CharucoFramePayload(
            annotated_frame_image=annotated_image,
            raw_frame_payload=raw_frame_payload,
            charuco_view_data=charuco_view_data
        )

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
    ## Jon, Run me to easily start a charuco board detect run
    print('starting main')
    BoardDetection().process()
