import logging
import time
import traceback
from pathlib import Path
from types import FunctionType
from typing import Any, Callable, Optional

import cv2
import numpy as np

from src.cameras.capture.frame_payload import FramePayload
from src.cameras.multicam_manager.cv_camera_manager import CVCameraManager
from src.cameras.persistence.video_writer.video_writer import SaveOptions
from src.core_processor.board_detection.base_pose_estimation import detect_charuco_board
from src.core_processor.board_detection.charuco_image_annotator import (
    annotate_image_with_charuco_data,
)
from src.core_processor.fps.fps_counter import FPSCamCounter
from src.core_processor.show_cam_window import show_cam_window
from src.core_processor.utils.image_fps_writer import write_fps_to_image

logger = logging.getLogger(__name__)


class BoardDetection:
    def __init__(self, cam_manager: CVCameraManager = CVCameraManager()):
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
                    response = self._process_single_cam_frame(cv_cam)
                    if cb and response.image is not None:
                        writer.write(
                            FramePayload(
                                image=response.image, timestamp=response.timestamp
                            )
                        )
                        await cb(response.image)
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
        self, show_window=True, post_processed_frame_cb=Callable[[FramePayload], None]
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
                        payload = self._process_single_cam_frame(cv_cam)
                        current_webcam_id = cv_cam.webcam_id_as_str

                        if payload is not None:
                            writer.write(payload)
                            if post_processed_frame_cb:
                                post_processed_frame_cb(payload)

                            fps_manager.increment_frame_processed_for(current_webcam_id)
                            if show_window:
                                should_continue = show_cam_window(
                                    current_webcam_id, payload.image, fps_manager
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

    def _process_single_cam_frame(self, cv_cam):
        success, frame, timestamp = cv_cam.latest_frame
        if not success:
            # logger.error("CV2 failed to grab a frame")
            return
        if frame is None:
            logger.error("Frame is empty")
            return
        (
            charuco_corners,
            charuco_ids,
            aruco_square_corners,
            aruco_square_ids,
        ) = detect_charuco_board(frame)
        # TODO - Pull out timestamps per frame and calculate fps to display on image
        success_bool = annotate_image_with_charuco_data(
            frame, cv_cam.webcam_id_as_str, charuco_corners, charuco_ids
        )
        cv2.polylines(frame, np.int32([charuco_corners]), True, (0, 100, 255), 2)
        return FramePayload(image=frame, timestamp=time.time_ns())


if __name__ == "__main__":
    ## Jon, Run me to easily start a charuco board detect run
    BoardDetection().process()
