import logging
from pathlib import Path
from typing import Union

import numpy as np

logger = logging.getLogger(__name__)


def load_mediapipe2d_data(output_data_folder_path: Union[str, Path]):
    mediapipe2d_xy_file_path = (
        Path(output_data_folder_path)
        / "mediapipe_2dData_numCams_numFrames_numTrackedPoints_pixelXY.npy"
    )
    logger.info(f"loading: {mediapipe2d_xy_file_path}")
    mediapipe2d_numCams_numFrames_numTrackedPoints_pixelXY = np.load(
        str(mediapipe2d_xy_file_path)
    )

    return mediapipe2d_numCams_numFrames_numTrackedPoints_pixelXY
