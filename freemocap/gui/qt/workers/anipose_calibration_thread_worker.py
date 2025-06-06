import logging
import threading
from pathlib import Path
from typing import Union

from PySide6.QtCore import Signal, QThread

from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import (
    CharucoBoardDefinition,
)
from freemocap.core_processes.capture_volume_calibration.run_anipose_capture_volume_calibration import (
    run_anipose_capture_volume_calibration,
)

logger = logging.getLogger(__name__)


class AniposeCalibrationThreadWorker(QThread):
    finished = Signal(str)
    in_progress = Signal(str)
    groundplane_failed = Signal(str)

    def __init__(
        self,
        calibration_videos_folder_path: Union[str, Path],
        charuco_square_size: Union[int, float],
        kill_thread_event: threading.Event,
        charuco_board_definition: CharucoBoardDefinition,
        use_charuco_as_groundplane: bool = False,
    ):
        super().__init__()
        logger.info(
            f"Initializing Anipose Calibration Thread Worker for videos in path {calibration_videos_folder_path}"
        )
        # if charuco_board_definition is None: #removing because with the new dropdown, we should always have a charuco board definition
        #     charuco_board_definition = CharucoBoardDefinition()

        self._kill_thread_event = kill_thread_event
        self._charuco_board_definition = charuco_board_definition
        self._charuco_square_size = charuco_square_size
        self._calibration_videos_folder_path = calibration_videos_folder_path
        self._use_charuco_as_groundplane = use_charuco_as_groundplane
        self._work_done = False

    @property
    def work_done(self):
        return self._work_done

    def _emit_in_progress_data(self, message: str):
        self.in_progress.emit(message)

    def run(self):
        logger.info("Beginning Anipose calibration with Charuco Square Size (mm): {}".format(self._charuco_square_size))

        try:
            toml_path, groundplane_success = run_anipose_capture_volume_calibration(
                charuco_board_definition=self._charuco_board_definition,
                charuco_square_size=self._charuco_square_size,
                calibration_videos_folder_path=self._calibration_videos_folder_path,
                pin_camera_0_to_origin=True,
                use_charuco_as_groundplane=self._use_charuco_as_groundplane,
                progress_callback=self._emit_in_progress_data,
            )
            self.finished.emit(str(toml_path))
            if groundplane_success:
                if groundplane_success.success is False:
                    self.groundplane_failed.emit(
                        f"Groundplane calibration failed: {groundplane_success.error} \n\n Using original camera calibration instead."
                    )

        except Exception as e:
            logger.exception("something went wrong in the anipose calibration")
            logger.exception(e)

        self._work_done = True

        logger.info("Anipose Calibration Complete")
