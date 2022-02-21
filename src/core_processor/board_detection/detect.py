import asyncio
import logging

import cv2
import numpy as np

from src.core_processor.board_detection.base_pose_estimation import detect_charuco_board
from src.core_processor.board_detection.charuco_image_annotator import (
    annotate_image_with_charuco_data,
)
from src.core_processor.processor import create_opencv_cams


class BoardDetection:
    async def process(self):
        logger = logging.getLogger(__name__)
        cv_cams = create_opencv_cams()

        for cv_cam in cv_cams:
            cv_cam.start_frame_capture()

        while True:
            exit_key = cv2.waitKey(1)
            if exit_key == 27:
                break
            for cv_cam in cv_cams:
                success, frame, timestamp = cv_cam.latest_frame()
                if not success:
                    continue

                if frame is None:
                    continue
                port_number = str(cv_cam.port_number)
                print(
                    f"got image of shape {frame.shape} from camera at port {port_number}"
                )
                (
                    charuco_corners,
                    charuco_ids,
                    aruco_square_corners,
                    aruco_square_ids,
                ) = detect_charuco_board(frame)
                # TODO - Pull out timestamps per frame and calculate fps to display on image
                success_bool = annotate_image_with_charuco_data(
                    frame, port_number, charuco_corners, charuco_ids
                )

                cv2.polylines(
                    frame, np.int32([charuco_corners]), True, (0, 100, 255), 2
                )

                cv2.imshow(port_number, frame)
                exit_key = cv2.waitKey(1)
                if exit_key == 27:
                    break


if __name__ == "__main__":
    ## Jon, Run me to easily start a charuco board detect run
    asyncio.run(BoardDetection().process())
