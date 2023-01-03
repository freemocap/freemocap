import logging
from pathlib import Path
from typing import Union

from PyQt6.QtCore import pyqtSignal, QThread

from freemocap.configuration.paths_and_files_names import get_calibrations_folder_path
from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import (
    CharucoBoardDefinition,
)
from old_src.core_processes.capture_volume_calibration.run_anipose_capture_volume_calibration import (
    run_anipose_capture_volume_calibration,
)

logger = logging.getLogger(__name__)


class AniposeCalibrationThreadWorker(QThread):
    finished = pyqtSignal()
    in_progress = pyqtSignal(str)

    def __init__(
        self,
        calibration_videos_folder_path: Union[str, Path],
        charuco_square_size: Union[int, float],
        charuco_board_definition: CharucoBoardDefinition = CharucoBoardDefinition(),
    ):
        super().__init__()
        self._charuco_board_definition = charuco_board_definition
        self._charuco_square_size = charuco_square_size
        self._calibration_videos_folder_path = calibration_videos_folder_path

        self._work_done = False

    @property
    def work_done(self):
        return self._work_done

    def _emit_in_progress_data(self, message: str):
        self.in_progress.emit(message)

    def run(self):
        logger.info(
            "Beginning Anipose calibration with Charuco Square Size (mm): {}".format(
                self._charuco_square_size
            )
        )

        try:
            run_anipose_capture_volume_calibration(
                charuco_board_definition=self._charuco_board_definition,
                charuco_square_size=self._charuco_square_size,
                calibration_videos_folder_path=self._calibration_videos_folder_path,
                pin_camera_0_to_origin=True,
                progress_callback=self._emit_in_progress_data,
                session_id=self._session_id,
            )
        except:
            logger.error("something failed in the anipose calibration")
            raise Exception

        logger.info("Anipose calibration complete")

        self.finished.emit()
        self._work_done = True
