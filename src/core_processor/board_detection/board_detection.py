import asyncio
import logging
import traceback

import cv2
import numpy as np

from src.cameras.cam_factory import close_all_cameras, create_opencv_cams
from src.core_processor.board_detection.base_pose_estimation import detect_charuco_board
from src.core_processor.board_detection.charuco_image_annotator import (
    annotate_image_with_charuco_data,
)
from src.core_processor.utils.image_fps_writer import write_fps_to_image

logger = logging.getLogger(__name__)


class BoardDetection:
    async def process_as_frame_loop(self, cb):
        cv_cams = create_opencv_cams()
        for cv_cam in cv_cams:
            cv_cam.start_frame_capture(save_video=True)

        while True:
            try:
                for cv_cam in cv_cams:
                    image = self._process_single_cam_frame(cv_cam)
                    if cb:
                        await cb(image, cv_cam.webcam_id_as_str)
            except:
                close_all_cameras(cv_cams)
                traceback.print_exc()

    async def process(self):
        """
        Opens Camera using OpenCV and begins image processing for charuco board
        If return images is true, the images are returned to the caller
        """
        cv_cams = create_opencv_cams()

        for cv_cam in cv_cams:
            cv_cam.start_frame_capture(save_video=True)

        try:
            while True:
                exit_key = cv2.waitKey(1)
                if exit_key == 27:
                    cv2.destroyAllWindows()
                    close_all_cameras(cv_cams)
                    break
                for cv_cam in cv_cams:
                    frame = self._process_single_cam_frame(cv_cam)
                    if frame is not None:
                        cv2.imshow(cv_cam.webcam_id_as_str, frame)
        except:
            close_all_cameras(cv_cams)
            cv2.destroyAllWindows()
            traceback.print_exc()

    def _process_single_cam_frame(self, cv_cam):
        success, frame, timestamp = cv_cam.latest_frame
        if not success:
            logger.error("CV2 failed to grab a frame")
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
        write_fps_to_image(frame, cv_cam.current_fps)
        return frame


if __name__ == "__main__":
    ## Jon, Run me to easily start a charuco board detect run
    asyncio.run(BoardDetection().process())
