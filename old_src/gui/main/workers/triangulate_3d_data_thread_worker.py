import logging
from pathlib import Path
from typing import Union

import numpy as np
from PyQt6.QtCore import pyqtSignal, QThread

from old_src.core_processes.capture_volume_calibration.triangulate_3d_data import (
    triangulate_3d_data,
)

logger = logging.getLogger(__name__)


class Triangulate3dDataThreadWorker(QThread):
    finished = pyqtSignal()

    def __init__(
        self,
        anipose_calibration_object,
        mediapipe_2d_data: np.ndarray,
        output_data_folder_path: Union[str, Path],
        mediapipe_confidence_cutoff_threshold: float,
        use_triangulate_ransac: bool = False,
    ):
        super().__init__()
        self._anipose_calibration_object = anipose_calibration_object
        self._mediapipe_2d_data = mediapipe_2d_data
        self._output_data_folder_path = output_data_folder_path
        self._mediapipe_confidence_cutoff_threshold = (
            mediapipe_confidence_cutoff_threshold
        )
        self._use_triangulate_ransac = use_triangulate_ransac

    def run(self):
        logger.info(
            f"Triangulating 3d data (i.e. combining 2d skeleton data with camera calibration data to estimate 3d positions of tracked points"
        )

        triangulate_3d_data(
            anipose_calibration_object=self._anipose_calibration_object,
            mediapipe_2d_data=self._mediapipe_2d_data,
            output_data_folder_path=self._output_data_folder_path,
            mediapipe_confidence_cutoff_threshold=self._mediapipe_confidence_cutoff_threshold,
            use_triangulate_ransac=self._use_triangulate_ransac,
        )

        self.finished.emit()
