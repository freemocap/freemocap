import logging
import threading
from pathlib import Path

from PySide6.QtCore import Signal, QThread

from freemocap.core_processes.export_data.blender_stuff.export_to_blender.export_to_blender import export_to_blender

logger = logging.getLogger(__name__)


class ExportToBlenderThreadWorker(QThread):
    success = Signal(bool)
    in_progress = Signal(str)

    def __init__(
        self,
        recording_path: Path,
        blender_file_path: Path,
        blender_executable_path: Path,
        kill_thread_event: threading.Event,
    ):
        super().__init__()
        logger.debug("Initializing Export to Blender Thread Worker")
        self._kill_thread_event = kill_thread_event
        self.recording_path = recording_path
        self.blender_file_path = blender_file_path
        self.blender_executable_path = blender_executable_path

        self._work_done = False

    @property
    def work_done(self):
        return self._work_done

    def _emit_in_progress_data(self, message: str):
        self.in_progress.emit(message)

    def run(self):
        logger.info("Beginning to export to Blender")

        try:
            export_to_blender(
                recording_folder_path=self.recording_path,
                blender_file_path=self.blender_file_path,
                blender_exe_path=self.blender_executable_path,
            )
            self.success.emit(True)
            logger.debug("Blender Export Complete")
        except Exception as e:
            logger.exception("something went wrong in the Blender export")
            logger.error(e)
            self.success.emit(False)

        self._work_done = True
