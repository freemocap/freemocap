import logging
import os
import threading
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QLayout,
)

from freemocap.gui.qt.utilities.save_and_load_gui_state import GuiState, save_gui_state
from freemocap.gui.qt.workers.anipose_calibration_thread_worker import (
    AniposeCalibrationThreadWorker,
)

from freemocap.system.paths_and_filenames.path_getters import (
    get_gui_state_json_path,
    get_last_successful_calibration_toml_path,
)

logger = logging.getLogger(__name__)


class CalibrationControlPanel(QWidget):
    def __init__(
        self, get_active_recording_info: Callable, kill_thread_event: threading.Event, gui_state: GuiState, parent=None
    ):
        super().__init__(parent=parent)
        self.gui_state = gui_state
        self._has_a_toml_path = False
        self._calibration_toml_path = None
        self._get_active_recording_info = get_active_recording_info
        self._kill_thread_event = kill_thread_event

        self.parent = parent

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._calibration_toml_path = None
        self._kill_thread_event = kill_thread_event

        self._anipose_calibration_frame_worker = None
        self._user_selected_toml_path = None

        self._selected_calibration_toml_label = QLabel("")
        self._selected_calibration_toml_label.setWordWrap(True)

        self._layout.addWidget(self._selected_calibration_toml_label)

        self._radio_button_layout = self._create_radio_button_layout()
        self._radio_button_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.addLayout(self._radio_button_layout)
        self._layout.addStretch()

    @property
    def calibration_toml_path(self) -> str:
        return self._calibration_toml_path

    @property
    def radio_button_layout(self) -> QLayout:
        return self._radio_button_layout

    def _create_radio_button_layout(self):
        radio_button_form_layout = QFormLayout()

        radio_button_form_layout.addRow(self._create_use_most_recent_calibration_radio_button())

        radio_button_form_layout.addRow(self._create_load_calibration_from_file_radio_button())

        radio_button_form_layout.addRow(self._add_calibrate_from_active_recording_radio_button())

        self.update_calibration_toml_path()
        return radio_button_form_layout

    def _create_load_calibration_from_file_radio_button(self) -> QLayout:
        vbox_layout = QVBoxLayout()
        radio_button_push_button_layout = QHBoxLayout()
        vbox_layout.addLayout(radio_button_push_button_layout)

        self._load_calibration_from_file_radio_button = QRadioButton("Load calibration from file")
        radio_button_push_button_layout.addWidget(self._load_calibration_from_file_radio_button)
        self._load_calibration_from_file_radio_button.toggled.connect(self._handle_load_calibration_from_file_toggled)

        self._load_calibration_toml_dialog_button = QPushButton("Load TOML...")
        radio_button_push_button_layout.addWidget(self._load_calibration_toml_dialog_button)
        # self._load_calibration_toml_dialog_button.setStyleSheet("font-size: 10pt;")
        self._load_calibration_toml_dialog_button.clicked.connect(self.open_load_camera_calibration_toml_dialog)
        self._load_calibration_toml_dialog_button.setEnabled(False)

        return vbox_layout

    def update_calibration_toml_path(self, toml_path: str = None):
        if toml_path is None:
            if self._load_calibration_from_file_radio_button.isChecked():
                if self._user_selected_toml_path is not None:
                    toml_path = self._user_selected_toml_path
                else:
                    toml_path = self._check_active_recording_for_calibration_toml()

            elif self._use_most_recent_calibration_radio_button.isChecked():
                toml_path = get_last_successful_calibration_toml_path()

            elif self._calibrate_from_active_recording_radio_button.isChecked():
                toml_path = self._check_active_recording_for_calibration_toml()

            else:  # no button checked -> initialize
                toml_path = self._check_active_recording_for_calibration_toml()
                if toml_path is not None:
                    self._load_calibration_from_file_radio_button.setChecked(True)
                else:
                    toml_path = get_last_successful_calibration_toml_path()
                    self._use_most_recent_calibration_radio_button.setChecked(True)

        self._calibration_toml_path = toml_path

        if self._calibration_toml_path is not None:
            logger.info(f"Setting calibration TOML path: {self._calibration_toml_path}")
            self._show_selected_calibration_toml_path(self._calibration_toml_path)
        else:
            self._show_selected_calibration_toml_path("-Calibration File Not Found-")

    def _add_calibrate_from_active_recording_radio_button(self):
        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)

        self._calibrate_from_active_recording_radio_button = QRadioButton("Calibrate from Active Recording")
        hbox.addWidget(self._calibrate_from_active_recording_radio_button)

        self._calibrate_from_active_recording_radio_button.toggled.connect(
            self._handle_calibrate_from_active_recording_toggled
        )

        self._calibrate_from_active_recording_button = QPushButton("Run calibration...")
        hbox.addWidget(self._calibrate_from_active_recording_button)

        self._calibrate_from_active_recording_button.setEnabled(False)
        self._calibrate_from_active_recording_button.clicked.connect(self.calibrate_from_active_recording)

        self._charuco_square_size_form_layout = self._create_charuco_square_size_form_layout()
        hbox2 = QHBoxLayout()
        hbox2.addStretch()
        hbox2.addLayout(self._charuco_square_size_form_layout)
        vbox.addLayout(hbox2)
        self._set_charuco_square_size_form_layout_visibility(False)

        return vbox

    def _create_use_most_recent_calibration_radio_button(self):
        self._use_most_recent_calibration_radio_button = QRadioButton("Use most recent calibration")

        self._use_most_recent_calibration_radio_button.toggled.connect(self._handle_use_most_recent_calibration_toggled)

        self._use_most_recent_calibration_radio_button.setToolTip(get_last_successful_calibration_toml_path())

        return self._use_most_recent_calibration_radio_button

    def update_calibrate_from_active_recording_button_text(self):
        active_recording_info = self._get_active_recording_info()
        if active_recording_info is None:
            active_path_str = "- No active recording selected -"
        else:
            if not active_recording_info.synchronized_videos_status_check:
                active_path_str = f"Recording: {active_recording_info.name} has no synchronized videos!"
            else:
                active_path_str = f"Calibrate from Recording: {self._get_active_recording_info().name}"

        self._calibrate_from_active_recording_button.setToolTip(active_path_str)
        self.update_calibration_toml_path()

    def _handle_use_most_recent_calibration_toggled(self, checked):
        pass
        # if checked:
        #     self._most_recent_calibration_path_label.show()
        # else:
        #     self._most_recent_calibration_path_label.hide()
        self.update_calibration_toml_path()

    def _handle_load_calibration_from_file_toggled(self, checked):
        if checked:
            self._load_calibration_toml_dialog_button.setEnabled(True)
        else:
            self._load_calibration_toml_dialog_button.setEnabled(False)

        self.update_calibration_toml_path()

    def _handle_calibrate_from_active_recording_toggled(self, checked):
        active_recording_info = self._get_active_recording_info()
        self.update_calibrate_from_active_recording_button_text()
        self.update_calibration_toml_path()

        if checked and active_recording_info is not None and active_recording_info.synchronized_videos_status_check:
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

    def open_load_camera_calibration_toml_dialog(self) -> str:
        # from this tutorial - https://www.youtube.com/watch?v=gg5TepTc2Jg&t=649s
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)

        calibration_toml_path_selection = dialog.getOpenFileName(
            self,
            "Select 'toml' containing camera calibration info",
            str(self._get_active_recording_info().path),
            "Camera Calibration TOML (*.toml)",
        )
        if len(calibration_toml_path_selection) > 0:
            self._user_selected_toml_path = calibration_toml_path_selection[0]
            logger.info(f"User selected camera calibration toml path:{self._user_selected_toml_path}")
            self._show_selected_calibration_toml_path(self._user_selected_toml_path)
            self.update_calibration_toml_path(toml_path=self._user_selected_toml_path)
            return self._user_selected_toml_path

    def _show_selected_calibration_toml_path(self, calibration_toml_path_str: str):
        self._calibration_toml_path = calibration_toml_path_str
        path = calibration_toml_path_str.replace(os.sep, "/ ")
        self._selected_calibration_toml_label.setText(path)
        self._selected_calibration_toml_label.show()

    def _create_charuco_square_size_form_layout(self):
        charuco_square_size_form_layout = QFormLayout()

        self._charuco_square_size_line_edit = QLineEdit()
        self._charuco_square_size_line_edit.setValidator(QDoubleValidator())
        self._charuco_square_size_line_edit.setFixedWidth(100)

        self._charuco_square_size_label = QLabel("Charuco square size (mm)")
        self._charuco_square_size_label.setStyleSheet("QLabel { font-size: 12px;  }")

        self._charuco_square_size_line_edit.setText(str(self.gui_state.charuco_square_size))
        self._charuco_square_size_line_edit.setToolTip(
            "The length of one of the edges of the black squares in the calibration board in mm"
        )
        self._charuco_square_size_line_edit.textChanged.connect(self._on_charuco_square_size_line_edit_changed)
        charuco_square_size_form_layout.addRow(self._charuco_square_size_label, self._charuco_square_size_line_edit)
        charuco_square_size_form_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        return charuco_square_size_form_layout

    def _on_charuco_square_size_line_edit_changed(self):
        self.gui_state.charuco_square_size = float(self._charuco_square_size_line_edit.text())
        save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())

    def calibrate_from_active_recording(self, charuco_square_size_mm: float = None):
        if not charuco_square_size_mm:
            charuco_square_size_mm = float(self._charuco_square_size_line_edit.text())

        active_recording_info = self._get_active_recording_info()
        if active_recording_info is None:
            logger.error("Cannot calibrate from active recording - no active recording selected")
            return

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
            charuco_square_size=float(charuco_square_size_mm),
            kill_thread_event=self._kill_thread_event,
        )

        self._anipose_calibration_frame_worker.start()

        self._anipose_calibration_frame_worker.finished.connect(self.update_calibration_toml_path)

    def _check_active_recording_for_calibration_toml(self):
        active_rec = self._get_active_recording_info()
        if active_rec is not None:
            if active_rec.calibration_toml_check:
                return self._get_active_recording_info().calibration_toml_path


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = CalibrationControlPanel()
    widget.show()
    sys.exit(app.exec())
