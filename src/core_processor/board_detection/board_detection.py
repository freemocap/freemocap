import logging
import traceback

import cv2
import numpy as np

from src.cameras.cv_camera_manager import CVCameraManager
from src.core_processor.board_detection.base_pose_estimation import detect_charuco_board
from src.core_processor.board_detection.charuco_image_annotator import (
    annotate_image_with_charuco_data,
)
from src.core_processor.utils.image_fps_writer import write_fps_to_image

logger = logging.getLogger(__name__)


class BoardDetection:
    def __init__(self, cam_manager: CVCameraManager = CVCameraManager()):
        self._cam_manager = cam_manager

    async def process_by_cam_id(self, webcam_id: str, cb):
        with self._cam_manager.start_capture_session(webcam_id) as cv_cam:
            try:
                while True:
                    if not cv_cam.is_capturing_frames:
                        return
                    image = self._process_single_cam_frame(cv_cam)
                    if cb and image is not None:
                        await cb(image)
            except:
                logger.error("Printing traceback")
                traceback.print_exc()

    def process(self):
        """
        Opens Camera using OpenCV and begins image processing for charuco board
        If return images is true, the images are returned to the caller
        """
        cam_manager: CVCameraManager = CVCameraManager()
        cv_cams = cam_manager.cv_cams

        # if its already capturing frames, this is a no-op
        with cam_manager.start_capture_session():
            try:
                while True:
                    exit_key = cv2.waitKey(1)
                    if exit_key == 27:
                        logger.info("ESC has been pressed.")
                        break
                    for cv_cam in cv_cams:
                        frame = self._process_single_cam_frame(cv_cam)
                        if frame is not None:
                            cv2.imshow(cv_cam.webcam_id_as_str, frame)
            except:
                logger.error("Printing traceback")
                traceback.print_exc()
            finally:
                for cv_cam in cv_cams:
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
        write_fps_to_image(frame, cv_cam.current_fps_short)
        return frame


if __name__ == "__main__":
    ## Jon, Run me to easily start a charuco board detect run
    # asyncio.run(BoardDetection().process())
    BoardDetection().process()
