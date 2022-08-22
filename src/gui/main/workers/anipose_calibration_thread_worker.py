from typing import Union

from PyQt6.QtCore import QThread, pyqtSignal

from src.pipelines.calibration_pipeline.calibration_pipeline_orchestrator import (
    CalibrationPipelineOrchestrator,
)


class AniposeCalibrationThreadWorker(QThread):
    finished = pyqtSignal()
    in_progress = pyqtSignal(str)

    def __init__(self, session_id: str, charuco_square_size_mm: Union[int, float]):
        super().__init__()
        self._session_id = session_id
        self._charuco_square_size_mm = charuco_square_size_mm

    @property
    def session_id(self):
        return self._session_id

    @session_id.setter
    def session_id(self, session_id: str):
        self._session_id = session_id

    def _emit_in_progress_data(self, message: str):
        self.in_progress.emit(message)

    def run(self):
        print("Beginning Anipose calibration")
        print("Session ID: {}".format(self._session_id))
        print("Charuco Square Size (mm): {}".format(self._charuco_square_size_mm))

        calibration_orchestrator = CalibrationPipelineOrchestrator(self._session_id)
        try:
            calibration_orchestrator.run_anipose_camera_calibration(
                charuco_square_size=self._charuco_square_size_mm,
                pin_camera_0_to_origin=True,
                progress_callback=self._emit_in_progress_data,
            )
        except:
            print("something failed in the anipose calibration")
            raise Exception
        print("Anipose calibration complete")

        self.finished.emit()
