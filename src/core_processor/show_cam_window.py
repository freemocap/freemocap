import logging

import cv2
import numpy as np

from src.core_processor.fps.fps_counter import FPSCamCounter
from src.core_processor.utils.image_fps_writer import write_fps_to_image

logger = logging.getLogger(__name__)


def show_cam_window(webcam_id: str, image: np.array, fps_counter_cls: FPSCamCounter):
    exit_key = cv2.waitKey(1)
    if exit_key == 27:
        logger.info("ESC has been pressed.")
        return False

    write_fps_to_image(
        image,
        fps_counter_cls.median_frames_per_second(webcam_id),
    )
    cv2.imshow(webcam_id, image)
    return True
