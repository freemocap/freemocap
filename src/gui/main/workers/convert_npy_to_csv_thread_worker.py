import logging
from pathlib import Path
from typing import Union

import numpy as np
from old_src.core_processes.mediapipe_stuff.convert_mediapipe_npy_to_csv import (
    convert_mediapipe_npy_to_csv,
)
from PyQt6.QtCore import pyqtSignal, QThread

logger = logging.getLogger(__name__)


class ConvertNpyToCsvThreadWorker(QThread):
    finished = pyqtSignal(str)

    def __init__(
        self,
        skel3d_frame_marker_xyz: np.ndarray,
        output_data_folder_path: Union[Path, str],
    ):
        super().__init__()
        self._skel3d_frame_marker_xyz = skel3d_frame_marker_xyz
        self.output_data_folder_path = output_data_folder_path

    def run(self):
        convert_mediapipe_npy_to_csv(
            mediapipe_3d_frame_trackedPoint_xyz=self._skel3d_frame_marker_xyz,
            output_data_folder_path=self.output_data_folder_path,
        )

        self.finished.emit("Done!")
