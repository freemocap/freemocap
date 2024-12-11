import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Signal, QThread

from freemocap.core_processes.export_data.blender_stuff.export_to_blender.export_to_blender import export_to_blender

logger = logging.getLogger(__name__)

def open_file(filename: str):
    if sys.platform == "win32":
        os.startfile(filename)  # noqa
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, filename])

def watch_for_blender_file(file_path: str,
                           stop_event: threading.Event,
                           interval: int = 1):
    last_modified_time = None
    while not stop_event.is_set():
        if os.path.exists(file_path):
            modified_time = os.path.getmtime(file_path)
            if last_modified_time is None or modified_time != last_modified_time:
                last_modified_time = modified_time
                open_file(file_path)
                stop_event.set()
        time.sleep(interval)

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
            # Start a new thread to watch the Blender file path
            watch_thread_stop_event = threading.Event()
            watcher_thread = threading.Thread(target=watch_for_blender_file, args=(str(self.blender_file_path),
                                                                                      watch_thread_stop_event))

            watcher_thread.daemon = True
            watcher_thread.start()

            export_to_blender(
                recording_folder_path=self.recording_path,
                blender_file_path=self.blender_file_path,
                blender_exe_path=self.blender_executable_path,
            )
            self.success.emit(True)

            watch_thread_stop_event.set()
            watcher_thread.join()
            logger.debug("Blender Export Complete")
        except Exception as e:
            logger.exception("something went wrong in the Blender export")
            logger.error(e)
            self.success.emit(False)

        self._work_done = True
