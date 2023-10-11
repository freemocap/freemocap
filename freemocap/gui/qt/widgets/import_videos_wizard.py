import logging
from pathlib import Path
import threading
from typing import Union
from skelly_synchronize import create_audio_debug_plots

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QListWidget,
    QLabel,
    QFormLayout,
    QLineEdit,
    QTreeView,
    QPushButton,
    QDialog,
    QCheckBox,
    QHBoxLayout,
)

from freemocap.gui.qt.workers.synchronize_videos_thread_worker import SynchronizeVideosThreadWorker

from freemocap.utilities.get_video_paths import get_video_paths
from freemocap.system.open_file import open_file
from freemocap.system.paths_and_filenames.file_and_folder_names import SYNCHRONIZED_VIDEOS_FOLDER_NAME
from freemocap.system.paths_and_filenames.path_getters import get_recording_session_folder_path

no_files_found_string = "No '.mp4' video files found! \n \n Note - We only look for `.mp4` files (for now). If your videos are a different format, convert them to `mp4` via online tools like `www.cloudconvert.com`, or softwares like `HandBrake`, `ffmpeg` or any video editing software"


logger = logging.getLogger(__name__)


class ImportVideosWizard(QDialog):
    folder_to_save_videos_to_selected = pyqtSignal(list, str, bool)

    def __init__(self, import_videos_path: Union[str, Path], kill_thread_event: threading.Event, parent=None):
        super().__init__(parent=parent)
        self.kill_thread_event = kill_thread_event

        self.setWindowTitle("Import Videos")

        self.import_videos_path = import_videos_path

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._import_directory_view = self._create_import_directory_view(import_videos_path)
        self._layout.addWidget(self._import_directory_view)

        self._video_file_paths = [str(path) for path in get_video_paths(path_to_video_folder=import_videos_path)]

        self._video_file_list_view = self._create_video_file_list_widget()
        self._layout.addWidget(self._video_file_list_view)

        self._form_layout = QFormLayout()
        self._layout.addLayout(self._form_layout)

        self._synchronize_videos_checkbox = QCheckBox("Synchronize videos by audio cross-correlation.")
        self._synchronize_videos_checkbox.toggled.connect(self._handle_synchronize_checkbox_toggled)

        synchronization_message = QLabel(
            "(Videos must have exactly the same video frame rates and audio sample rates to be synchronized.)"
        )
        synchronization_message.setWordWrap(True)

        synchronization_layout = QHBoxLayout()

        synchronization_layout.addWidget(self._synchronize_videos_checkbox)
        synchronization_layout.addWidget(synchronization_message)

        self._form_layout.addRow("Synchronize videos:", synchronization_layout)

        self._folder_name = f"import_{Path(import_videos_path).name}"
        self._folder_name_line_edit = QLineEdit(parent=self)
        self._folder_name_line_edit.textChanged.connect(self._handle_folder_name_line_edit_changed)

        self._folder_name_line_edit.setPlaceholderText(self._folder_name)
        self._form_layout.addRow("Recording Name:", self._folder_name_line_edit)

        self._folder_where_videos_will_be_saved_to_label = QLabel(self._get_folder_videos_will_be_saved_to())
        self._form_layout.addRow("Videos will be saved to:", self._folder_where_videos_will_be_saved_to_label)

        self._continue_button = QPushButton("Continue")
        self._continue_button.isDefault()
        self._continue_button.clicked.connect(self._handle_continue_button_clicked)
        self._form_layout.addRow(self._continue_button)

    def _get_folder_videos_will_be_saved_to(self):
        return str(Path(get_recording_session_folder_path()) / self._folder_name / SYNCHRONIZED_VIDEOS_FOLDER_NAME)

    def _create_import_directory_view(self, import_videos_path: Union[str, Path]):
        self._file_system_model = QFileSystemModel()
        self._file_system_model.setRootPath(str(import_videos_path))

        self._tree_view_widget = QTreeView()
        self._layout.addWidget(self._tree_view_widget)
        self._tree_view_widget.setModel(self._file_system_model)
        self._tree_view_widget.setRootIndex(self._file_system_model.index(str(import_videos_path)))
        self._tree_view_widget.setColumnWidth(0, 250)
        self._tree_view_widget.setHeaderHidden(False)
        self._tree_view_widget.setAlternatingRowColors(True)
        self._tree_view_widget.setWindowTitle(str(import_videos_path))

        self._tree_view_widget.doubleClicked.connect(self._open_file)

        return self._tree_view_widget

    def _open_file(self):
        index = self._tree_view_widget.currentIndex()
        file_path = self._file_system_model.filePath(index)
        logger.info(f"Opening file from file_system_view_widget: {file_path}")
        open_file(file_path)

    def _create_video_file_list_widget(self):
        list_view = QListWidget()
        list_view.setWordWrap(True)
        if len(self._video_file_paths) == 0:
            list_view.addItem(no_files_found_string)
        else:
            list_view.addItems(self._video_file_paths)
        return list_view

    def _handle_folder_name_line_edit_changed(self, event):
        self._folder_name = self._folder_name_line_edit.text()
        self._folder_where_videos_will_be_saved_to_label.setText(self._get_folder_videos_will_be_saved_to())

    def _handle_continue_button_clicked(self, event):
        if self._synchronize_videos_checkbox.isChecked():
            self.synchronize_videos_thread_worker = SynchronizeVideosThreadWorker(
                raw_video_folder_path=Path(self.import_videos_path),
                synchronized_video_folder_path=Path(self._get_folder_videos_will_be_saved_to()),
                kill_thread_event=self.kill_thread_event,
            )
            self.synchronize_videos_thread_worker.start()
            self.synchronize_videos_thread_worker.finished.connect(self._handle_video_synchronization_finished)
        else:
            self.folder_to_save_videos_to_selected.emit(
                self._video_file_paths, self._get_folder_videos_will_be_saved_to(), False
            )
        self.accept()

    def _handle_synchronize_checkbox_toggled(self, event):
        if self._synchronize_videos_checkbox.isChecked():
            logger.info("Synchronize videos by audio selected, videos will be synchronized before importing")
        else:
            logger.info("Synchronize videos by audio deselected, videos will not be synchronized")

    def _handle_video_synchronization_finished(self):
        self._video_file_paths = [
            str(path)
            for path in get_video_paths(path_to_video_folder=self.synchronize_videos_thread_worker.output_folder_path)
        ]

        create_audio_debug_plots(synchronized_video_folder_path=self.synchronize_videos_thread_worker.output_folder_path)

        self.folder_to_save_videos_to_selected.emit(
            self._video_file_paths, self._get_folder_videos_will_be_saved_to(), True
        )


if __name__ == "__main__":
    # from PyQt6.QtWidgets import QApplication
    # import sys
    #
    # app = QApplication(sys.argv)
    import_videos_window = ImportVideosWizard(import_videos_path=Path().home())
    import_videos_window.exec()
    # import_videos_window.show()
    # sys.exit(app.exec())
