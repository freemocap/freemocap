import logging
import multiprocessing

from PyQt6.QtCore import pyqtSignal, QThread

from freemocap.core_processes.process_motion_capture_videos.process_recording_folder import (
    process_recording_folder,
)
from freemocap.recording_models.post_processing_parameter_models import PostProcessingParameterModel

logger = logging.getLogger(__name__)


class ProcessMotionCaptureDataThreadWorker(QThread):
    finished = pyqtSignal()
    in_progress = pyqtSignal(str)

    def __init__(self, session_processing_parameters: PostProcessingParameterModel,
                 kill_event: multiprocessing.Event, parent=None):
        super().__init__()
        self._session_processing_parameters = session_processing_parameters
        self._kill_event = kill_event
        self._process = multiprocessing.Process(target=process_recording_folder, args=(self._session_processing_parameters, self._kill_event))

    def run(self):
        logger.info(
            f"Beginning processing of motion capture data with parameters: {self._session_processing_parameters.__dict__}"
        )
        self._kill_event.clear()

        try:
            self._process.start()
            self._process.join()
        except Exception as e:
            logger.error(f"Error processing motion capture data: {e}")


        logger.info("Finished processing session folder!")

        self.finished.emit()
