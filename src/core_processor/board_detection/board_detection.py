import asyncio
import logging

import cv2
import numpy as np

from src.cameras.cam_factory import create_opencv_cams
from src.core_processor.board_detection.base_pose_estimation import detect_charuco_board
from src.core_processor.board_detection.charuco_image_annotator import (
    annotate_image_with_charuco_data,
)


class BoardDetection:
    async def process(self):
        logger = logging.getLogger(__name__)
        cv_cams = create_opencv_cams()

        for cv_cam in cv_cams:
            cv_cam.start_frame_capture(save_video=True)

        while True:
            exit_key = cv2.waitKey(1)
            if exit_key == 27:
                cv2.destroyAllWindows()
                break
            for cv_cam in cv_cams:
                success, frame, timestamp = cv_cam.latest_frame()
                if not success:
                    logger.error("CV2 failed to grab a frame")
                    continue
                if frame is None:
                    logger.error("Frame is empty")
                    continue
                # print(
                #     f"got image of shape {frame.shape} from camera at port {port_number}"
                # )
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

                cv2.polylines(
                    frame, np.int32([charuco_corners]), True, (0, 100, 255), 2
                )
                self.apply_fps(frame, cv_cam.current_fps)
                cv2.imshow(cv_cam.webcam_id_as_str, frame)

    def apply_fps(self, image, fps_number):
        cv2.putText(
            image,
            f"FPS: {str(fps_number)}",
            (10, 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (209, 180, 0, 255),
            1,
        )


if __name__ == "__main__":
    ## Jon, Run me to easily start a charuco board detect run
    asyncio.run(BoardDetection().process())
