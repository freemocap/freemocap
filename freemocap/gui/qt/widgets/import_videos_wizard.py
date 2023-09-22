import logging
from pathlib import Path
import threading
from typing import Union
from skelly_synchronize import create_audio_debug_plots, create_brightness_debug_plots

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFileSystemModel, QDoubleValidator
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QLabel,
    QFormLayout,
    QLineEdit,
    QTreeView,
    QPushButton,
    QDialog,
    QCheckBox,
    QButtonGroup,
    QRadioButton,
    QWidget,
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

        self._synchronize_videos_checkbox = QCheckBox()
        self._synchronize_videos_checkbox.toggled.connect(self._handle_synchronize_checkbox_toggled)

        self.synchronization_extension = self._create_synchronization_extension()

        self._form_layout.addRow("Synchronize videos:", self._synchronize_videos_checkbox)
        self._form_layout.addRow(self.synchronization_extension)

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

    def _create_synchronization_extension(self):
        synchronization_extension = QWidget()

        self._synchronization_method_buttons = QButtonGroup(self)
        self._cross_correlation_radio_button = QRadioButton("Audio Cross Correlation")
        self._cross_correlation_radio_button.setChecked(True)
        self.synchronization_method = "audio"
        self._brightness_contrast_radio_button = QRadioButton("Brightness Contrast Detection")

        self._cross_correlation_radio_button.toggled.connect(self._handle_cross_correlation_radio_button_toggled)
        self._brightness_contrast_radio_button.toggled.connect(self._handle_brightness_contrast_radio_button_toggled)
        self._synchronization_method_buttons.addButton(self._cross_correlation_radio_button)
        self._synchronization_method_buttons.addButton(self._brightness_contrast_radio_button)

        extension_layout = QVBoxLayout()
        synch_button_layout = QHBoxLayout()
        synch_button_layout.addWidget(QLabel("Choose synchronization method:"))
        synch_button_layout.addWidget(self._cross_correlation_radio_button)
        synch_button_layout.addWidget(self._brightness_contrast_radio_button)

        synchronization_message = QLabel(
            " - Videos must have exactly the same video frame rates to be synchronized.\n\n - For audio cross correlation, audio tracks must have the same sample rate.\n"
        )
        synchronization_message.setWordWrap(True)

        line_edit_layout = QHBoxLayout()
        self.brightness_contrast_threshold_line_edit = QLineEdit("Brightness Contrast Threshold:")
        self.brightness_contrast_threshold_line_edit.setText("1000")
        self.brightness_contrast_threshold_line_edit.setEnabled(False)

        brightness_validator = QDoubleValidator()
        brightness_validator.setBottom(1)
        self.brightness_contrast_threshold_line_edit.setValidator(brightness_validator)

        line_edit_layout.addWidget(QLabel("Brightness Contrast Threshold:"))
        line_edit_layout.addWidget(self.brightness_contrast_threshold_line_edit)
        line_edit_layout.addWidget(QLabel("   Only applies to brightness contrast detection"))

        extension_layout.addLayout(synch_button_layout)
        extension_layout.addWidget(synchronization_message)
        extension_layout.addLayout(line_edit_layout)

        synchronization_extension.setLayout(extension_layout)

        synchronization_extension.hide()

        return synchronization_extension

    def _handle_folder_name_line_edit_changed(self, event):
        self._folder_name = self._folder_name_line_edit.text()
        self._folder_where_videos_will_be_saved_to_label.setText(self._get_folder_videos_will_be_saved_to())

    def _handle_continue_button_clicked(self, event):
        if self._synchronize_videos_checkbox.isChecked():
            self.synchronize_videos_thread_worker = SynchronizeVideosThreadWorker(
                raw_video_folder_path=Path(self.import_videos_path),
                synchronized_video_folder_path=Path(self._get_folder_videos_will_be_saved_to()),
                kill_thread_event=self.kill_thread_event,
                synchronization_method=self.synchronization_method,
                brightness_contrast_threshold=float(self.brightness_contrast_threshold_line_edit.text()),
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
            logger.info("Synchronize videos selected, videos will be synchronized before importing")
            self.synchronization_extension.setVisible(True)
        else:
            logger.info("Synchronize videos deselected, videos will not be synchronized")
            self.synchronization_extension.setVisible(False)

    def _handle_cross_correlation_radio_button_toggled(self, event):
        if self._cross_correlation_radio_button.isChecked():
            self.synchronization_method = "audio"

    def _handle_brightness_contrast_radio_button_toggled(self, event):
        if self._brightness_contrast_radio_button.isChecked():
            self.synchronization_method = "brightness"
            self.brightness_contrast_threshold_line_edit.setEnabled(True)
        else:
            self.brightness_contrast_threshold_line_edit.setEnabled(False)

    def _handle_video_synchronization_finished(self):
        self._video_file_paths = [
            str(path)
            for path in get_video_paths(path_to_video_folder=self.synchronize_videos_thread_worker.output_folder_path)
        ]
        if self.synchronization_method == "audio":
            create_audio_debug_plots(
                synchronized_video_folder_path=self.synchronize_videos_thread_worker.output_folder_path
            )
        if self.synchronization_method == "brightness":
            create_brightness_debug_plots(
                raw_video_folder_path=self.import_videos_path,
                synchronized_video_folder_path=self.synchronize_videos_thread_worker.output_folder_path,
            )
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
