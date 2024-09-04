import logging
import multiprocessing
import time
from pathlib import Path

from PySide6.QtCore import Signal, QThread

from freemocap.core_processes.process_motion_capture_videos.process_recording_folder import process_recording_folder
from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel
from freemocap.system.paths_and_filenames.file_and_folder_names import RECORDING_PARAMETERS_JSON_FILE_NAME
from freemocap.utilities.save_dictionary_to_json import save_dictionary_to_json

logger = logging.getLogger(__name__)


class ProcessMotionCaptureDataThreadWorker(QThread):
    finished = Signal(bool)
    in_progress = Signal(object)

    def __init__(
        self, post_processing_parameters: ProcessingParameterModel, kill_event: multiprocessing.Event, parent=None
    ):
        super().__init__()
        self._processing_parameters = post_processing_parameters
        self._kill_event = kill_event

        self._queue = multiprocessing.Queue()

        self._process = multiprocessing.Process(
            target=process_recording_folder, args=(self._processing_parameters, self._kill_event, self._queue)
        )
        self._success = None

    def run(self):
        logger.info(
            f"Beginning processing of motion capture data with parameters: {self._processing_parameters.dict(exclude={'tracking_model_info'})}"
        )
        self._kill_event.clear()

        recording_info_dict = self._processing_parameters.dict(exclude={"recording_info_model"})
        Path(self._processing_parameters.recording_info_model.output_data_folder_path).mkdir(
            parents=True, exist_ok=True
        )

        save_dictionary_to_json(
            save_path=self._processing_parameters.recording_info_model.output_data_folder_path,
            file_name=RECORDING_PARAMETERS_JSON_FILE_NAME,
            dictionary=recording_info_dict,
        )

        try:
            self._process.start()
            while self._process.is_alive():
                time.sleep(0.01)
                if self._queue.empty():
                    continue
                else:
                    record = self._queue.get()
                    print(f"message: {record.msg}")
                    self.in_progress.emit(record)

            while not self._queue.empty():
                record = self._queue.get()
                print(f"message: {record.msg}")
                self.in_progress.emit(record)

            self._success = True
            logger.info("Finished processing session folder!")

        except Exception as e:  # noqa
            record = self._queue.get()
            logger.error(f"Error processing session folder: {str(record)}")
            self._success = False

        self.finished.emit(self._success)
