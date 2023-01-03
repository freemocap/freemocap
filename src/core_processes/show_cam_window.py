import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def show_cam_window(
    webcam_id: str,
    image: np.array,
):
    cv2.imshow(webcam_id, image)
    return True
