from pathlib import Path
from typing import Union

from PyQt6.QtCore import QThread, pyqtSignal

from src.cameras.detection.cam_singleton import get_or_create_cams
from src.cameras.detection.models import FoundCamerasResponse

import logging

from src.export_stuff.blender_stuff.export_to_blender import export_to_blender

logger = logging.getLogger(__name__)


class ExportToBlenderThreadWorker(QThread):
    finished = pyqtSignal(str)

    def __init__(self, session_folder_path: Union[str, Path]):
        super().__init__()
        self._session_folder_path = session_folder_path

    def run(self):
        logger.info("Starting `export_to_blender` thread worker...")
        blender_file_path = export_to_blender(self._session_folder_path)
        self.finished.emit(blender_file_path)
