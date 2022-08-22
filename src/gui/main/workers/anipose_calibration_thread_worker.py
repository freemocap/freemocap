import logging
from pathlib import Path
from typing import Union

from PyQt6.QtCore import QThread, pyqtSignal

from src.core_processes.capture_volume_calibration.run_anipose_capture_volume_calibration import (
    run_anipose_capture_volume_calibration,
)

logger = logging.getLogger(__name__)


class AniposeCalibrationThreadWorker(QThread):
    finished = pyqtSignal()
    in_progress = pyqtSignal(str)

    def __init__(
        self,
        calibration_videos_folder_path: Union[str, Path],
        charuco_square_size_mm: Union[int, float],
    ):
        super().__init__()
        self._charuco_square_size_mm = charuco_square_size_mm
        self._calibration_videos_folder_path = calibration_videos_folder_path

    def _emit_in_progress_data(self, message: str):
        self.in_progress.emit(message)

    def run(self):
        logger.info(
            "Beginning Anipose calibration with Charuco Square Size (mm): {}".format(
                self._charuco_square_size_mm
            )
        )

        try:
            run_anipose_capture_volume_calibration(
                charuco_square_size=self._charuco_square_size_mm,
                calibration_videos_folder_path=self._calibration_videos_folder_path,
                pin_camera_0_to_origin=True,
                progress_callback=self._emit_in_progress_data,
            )
        except:
            logger.error("something failed in the anipose calibration")
            raise Exception

        logger.info("Anipose calibration complete")

        self.finished.emit()
