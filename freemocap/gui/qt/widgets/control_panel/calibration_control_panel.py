import logging
from pathlib import Path
from typing import Callable, Union

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from freemocap.configuration.paths_and_files_names import (
    get_last_successful_calibration_toml_path,
    get_calibrations_folder_path,
)
from freemocap.core_processes.capture_volume_calibration.charuco_stuff.default_charuco_square_size import (
    default_charuco_square_size_mm,
)
from freemocap.gui.qt.workers.anipose_calibration_thread_worker import (
    AniposeCalibrationThreadWorker,
)

logger = logging.getLogger(__name__)


class CalibrationControlPanel(QWidget):
    def __init__(self, get_active_recording_info_callable: Callable, parent=None):
        super().__init__(parent=parent)
        self._get_active_recording_info_callable = get_active_recording_info_callable
        self.parent = parent

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._radio_button_layout = self._create_radio_button_layout()
        self._radio_button_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.addLayout(self._radio_button_layout)
        self._layout.addStretch()

        self._anipose_calibration_frame_worker = None

    def _create_radio_button_layout(self):
        radio_button_form_layout = QFormLayout()

        self._add_use_most_recent_calibration_radio_button(radio_button_form_layout)

        self._add_load_calibration_from_file_radio_button(radio_button_form_layout)

        self._add_calibrate_from_active_recording_radio_button(radio_button_form_layout)

        return radio_button_form_layout

    def _add_use_most_recent_calibration_radio_button(self, radio_button_layout: QFormLayout):

        self._use_most_recent_calibration_radio_button = QRadioButton("Use most recent calibration")
        self._use_most_recent_calibration_radio_button.setChecked(True)
        self._use_most_recent_calibration_radio_button.toggled.connect(self._handle_use_most_recent_calibration_toggled)

        radio_button_layout.addWidget(self._use_most_recent_calibration_radio_button)
        self._use_most_recent_calibration_radio_button.setToolTip(get_last_successful_calibration_toml_path())
        self._use_most_recent_calibration_radio_button.setToolTip(get_last_successful_calibration_toml_path())

    def _add_load_calibration_from_file_radio_button(self, radio_button_form_layout: QFormLayout):
        self._load_calibration_from_file_radio_button = QRadioButton("Load calibration from file")
        self._load_calibration_from_file_radio_button.toggled.connect(self._handle_load_calibration_from_file_toggled)
        radio_button_form_layout.addWidget(self._load_calibration_from_file_radio_button)

        self._user_selected_calibration_toml_path_label = QLabel("--No Calibration Path Selected--")
        self._user_selected_calibration_toml_path_label.setWordWrap(True)
        radio_button_form_layout.addWidget(self._user_selected_calibration_toml_path_label)
        self._user_selected_calibration_toml_path_label.setEnabled(False)

        self._load_calibration_toml_dialog_button = QPushButton("Load Camera Calibration TOML...")
        # self._load_calibration_toml_dialog_button.setStyleSheet("font-size: 10pt;")
        self._load_calibration_toml_dialog_button.clicked.connect(self._open_load_camera_calibration_toml_dialog)
        radio_button_form_layout.addWidget(self._load_calibration_toml_dialog_button)
        self._load_calibration_toml_dialog_button.setEnabled(False)

    def _add_calibrate_from_active_recording_radio_button(self, radio_button_form_layout: QFormLayout):
        self._calibrate_from_active_recording_radio_button = QRadioButton("Calibrate from active recording")
        radio_button_form_layout.addWidget(self._calibrate_from_active_recording_radio_button)

        self._calibrate_from_active_recording_radio_button.toggled.connect(
            self._handle_calibrate_from_active_recording_toggled
        )

        self._calibrate_from_active_recording_button = QPushButton(".")
        self.update_calibrate_from_active_recording_button_text()
        self._calibrate_from_active_recording_button.setEnabled(False)
        self._calibrate_from_active_recording_button.clicked.connect(self._calibrate_from_active_recording)
        radio_button_form_layout.addWidget(self._calibrate_from_active_recording_button)

        self._charuco_square_size_form_layout = self._create_charuco_square_size_form_layout()
        radio_button_form_layout.addRow(self._charuco_square_size_form_layout)
        self._set_charuco_square_size_form_layout_visibility(False)

    def update_calibrate_from_active_recording_button_text(self):
        if self._get_active_recording_info_callable() is None:
            active_path_str = f"- No active recording selected -"
        else:
            active_path_str = f"Calibrate from Recording: {self._get_active_recording_info_callable().name}"

        self._calibrate_from_active_recording_button.setText(active_path_str)

    def _handle_use_most_recent_calibration_toggled(self, checked):
        pass
        # if checked:
        #     self._most_recent_calibration_path_label.show()
        # else:
        #     self._most_recent_calibration_path_label.hide()

    def _handle_load_calibration_from_file_toggled(self, checked):
        if checked:
            self._load_calibration_toml_dialog_button.setEnabled(True)
            self._user_selected_calibration_toml_path_label.setEnabled(True)
        else:
            self._load_calibration_toml_dialog_button.setEnabled(False)
            self._user_selected_calibration_toml_path_label.setEnabled(False)

    def _handle_calibrate_from_active_recording_toggled(self, checked):
        self.update_calibrate_from_active_recording_button_text()
        if checked:
            self._calibrate_from_active_recording_button.setEnabled(True)
            self._set_charuco_square_size_form_layout_visibility(True)
        else:
            self._calibrate_from_active_recording_button.setEnabled(False)
            self._set_charuco_square_size_form_layout_visibility(False)

    def _set_charuco_square_size_form_layout_visibility(self, visible):
        label_index = self._charuco_square_size_form_layout.indexOf(self._charuco_square_size_label)
        line_edit_index = self._charuco_square_size_form_layout.indexOf(self._charuco_square_size_line_edit)
        if visible:
            self._charuco_square_size_form_layout.itemAt(label_index).widget().setEnabled(True)
            self._charuco_square_size_form_layout.itemAt(line_edit_index).widget().setEnabled(True)
        else:
            self._charuco_square_size_form_layout.itemAt(label_index).widget().setEnabled(False)
            self._charuco_square_size_form_layout.itemAt(line_edit_index).widget().setEnabled(False)

    def _open_load_camera_calibration_toml_dialog(self):
        # from this tutorial - https://www.youtube.com/watch?v=gg5TepTc2Jg&t=649s
        calibration_toml_path_selection = QFileDialog.getOpenFileName(
            self,
            "Select 'toml' containing camera calibration info",
            str(get_calibrations_folder_path()),
            "Camera Calibration TOML (*.toml)",
        )
        self.calibration_toml_path_str = calibration_toml_path_selection[0]
        logger.info(f"User selected camera calibration toml path:{self.calibration_toml_path_str}")
        self._user_selected_calibration_toml_path_label.setText(self.calibration_toml_path_str)

    def _create_charuco_square_size_form_layout(self):
        charuco_square_size_form_layout = QFormLayout()
        self._charuco_square_size_line_edit = QLineEdit()
        self._charuco_square_size_label = QLabel("Charuco square size (mm)")
        self._charuco_square_size_line_edit.setText(str(default_charuco_square_size_mm))
        self._charuco_square_size_line_edit.setToolTip(
            "The length of one of the edges of the black squares in the calibration board in mm"
        )
        charuco_square_size_form_layout.addRow(self._charuco_square_size_label, self._charuco_square_size_line_edit)
        return charuco_square_size_form_layout

    def _calibrate_from_active_recording(self):
        active_recording_info = self._get_active_recording_info_callable()
        logger.info(f"Calibrating from active recording: {active_recording_info.name}")

        if not active_recording_info.synchronized_videos_status_check:
            logger.error(
                f"Cannot calibrate from {active_recording_info.name} -"
                f" `active_recording_info.synchronized_videos_status_check` is "
                f"{active_recording_info.synchronized_videos_status_check}"
            )

            return
        self._anipose_calibration_frame_worker = AniposeCalibrationThreadWorker(
            calibration_videos_folder_path=active_recording_info.synchronized_videos_folder_path,
            charuco_square_size=float(self._charuco_square_size_line_edit.text()),
        )

        self._anipose_calibration_frame_worker.start()

        self._calibrate_from_active_recording_button.setEnabled(False)
        self._anipose_calibration_frame_worker.finished.connect(
            lambda: self._calibrate_from_active_recording_button.setEnabled(True)
        )


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = CalibrationControlPanel()
    widget.show()
    sys.exit(app.exec())
