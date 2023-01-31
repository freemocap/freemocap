import logging

from PyQt6.QtCore import pyqtSignal, QThread

from freemocap.core_processes.process_motion_capture_videos.process_session_folder import (
    process_session_folder,
)
from freemocap.parameter_info_models.recording_processing_parameter_models import RecordingProcessingParameterModel

logger = logging.getLogger(__name__)


class ProcessMotionCaptureDataThreadWorker(QThread):
    finished = pyqtSignal()
    in_progress = pyqtSignal(str)

    def __init__(self, session_processing_parameters: RecordingProcessingParameterModel):
        super().__init__()
        self._session_processing_parameters = session_processing_parameters

    @property
    def work_done(self):
        return self._work_done

    def _emit_in_progress_data(self, message: str):
        self.in_progress.emit(message)

    def run(self):
        logger.info(
            f"Beginning processing of motion capture data with parameters: {self._session_processing_parameters.__dict__}"
        )

        process_session_folder(
            session_processing_parameter_model=self._session_processing_parameters,
        )

        logger.info("Finished processing session folder!")

        self.finished.emit()
        self._work_done = True
