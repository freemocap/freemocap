from pathlib import Path
from typing import Union, List

from PyQt6.QtCore import QThread, pyqtSignal


import logging

from src.core_processes.mediapipe_2d_skeleton_detector.mediapipe_skeleton_detector import (
    MediaPipeSkeletonDetector,
)

logger = logging.getLogger(__name__)


class Mediapipe2dDetectionThreadWorker(QThread):
    finished = pyqtSignal()

    def __init__(
        self,
        path_to_folder_of_videos_to_process: Union[str, Path],
        output_data_folder_path: Union[str, Path],
    ):
        super().__init__()
        self._path_to_folder_of_videos_to_process = path_to_folder_of_videos_to_process
        self._output_data_folder_path = output_data_folder_path

    def run(self):
        logger.info(f"Tracking 2D mediapipe skeletons in videos ")
        mediapipe_skeleton_detector = MediaPipeSkeletonDetector()
        mediapipe_skeleton_detector.process_folder_full_of_videos(
            self._path_to_folder_of_videos_to_process, self._output_data_folder_path
        )

        self.finished.emit()
