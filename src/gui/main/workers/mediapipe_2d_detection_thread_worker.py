from pathlib import Path
from typing import Union, List

from PyQt6.QtCore import QThread, pyqtSignal

from src.cameras.detection.cam_singleton import get_or_create_cams
from src.cameras.detection.models import FoundCamerasResponse

import logging

from src.core_processor.mediapipe_skeleton_detector.mediapipe_skeleton_detector import (
    MediaPipeSkeletonDetector,
)

logger = logging.getLogger(__name__)


class Mediapipe2dDetectionThreadWorker(QThread):
    finished = pyqtSignal(str)

    def __init__(self, path_to_folder_of_videos_to_process: Union[str, Path]):
        super().__init__()
        self._path_to_folder_of_videos_to_process = path_to_folder_of_videos_to_process

    def run(self):
        logger.info(f"tracking 2D mediapipe skeletons in videos ")
        mediapipe_skeleton_detector = MediaPipeSkeletonDetector()
        mediapipe_skeleton_detector.process_folder_full_of_videos(
            self._path_to_folder_of_videos_to_process
        )

        self.finished.emit("hi")
