import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class CalibrationControlPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._add_use_most_recent_calibration_radio_button()

        self._add_load_calibration_from_file_radio_button()

        self._add_calibrate_from_last_recording_radio_button()

    def _add_use_most_recent_calibration_radio_button(self):
        self._use_most_recent_calibration_radio_button = QRadioButton(
            "Use most recent calibration"
        )
        self._use_most_recent_calibration_radio_button.setChecked(True)
        self._use_most_recent_calibration_radio_button.toggled.connect(
            self._handle_use_most_recent_calibration_toggled
        )
        self._layout.addWidget(self._use_most_recent_calibration_radio_button)

        self._most_recent_calibration_path = QLabel("--Most recent calibration path--")
        self._layout.addWidget(self._most_recent_calibration_path)

    def _add_load_calibration_from_file_radio_button(self):
        self._load_calibration_from_file_radio_button = QRadioButton(
            "Load calibration from file"
        )
        self._load_calibration_from_file_radio_button.toggled.connect(
            self._handle_load_calibration_from_file_toggled
        )
        self._layout.addWidget(self._load_calibration_from_file_radio_button)

        self._load_calibration_toml_dialog_button = QPushButton(
            "Load Camera Calibration TOML..."
        )
        self._load_calibration_toml_dialog_button.clicked.connect(
            self._open_load_camera_calibration_toml_dialog
        )
        self._layout.addWidget(self._load_calibration_toml_dialog_button)
        self._load_calibration_toml_dialog_button.hide()

        self._user_selected_calibration_toml_path = QLabel("--Calibration TOML path--")
        self._layout.addWidget(self._user_selected_calibration_toml_path)
        self._user_selected_calibration_toml_path.hide()

    def _add_calibrate_from_last_recording_radio_button(self):
        self._record_new_calibration_radio_button = QRadioButton(
            "Calibrate from last recording"
        )
        self._record_new_calibration_radio_button.toggled.connect(
            self._handle_calibrate_from_last_recording_toggled
        )
        self._layout.addWidget(self._record_new_calibration_radio_button)

        self._record_new_calibration_button = QPushButton(
            "Calibrate from last recording"
        )
        self._record_new_calibration_button.clicked.connect(
            self._calibrate_from_previous_recording
        )
        self._layout.addWidget(self._record_new_calibration_button)
        self._record_new_calibration_button.hide()

    def _handle_use_most_recent_calibration_toggled(self, checked):
        if checked:
            self._most_recent_calibration_path.show()
        else:
            self._most_recent_calibration_path.hide()

    def _handle_load_calibration_from_file_toggled(self, checked):
        if checked:
            self._load_calibration_toml_dialog_button.show()
            self._user_selected_calibration_toml_path.show()
        else:
            self._load_calibration_toml_dialog_button.hide()
            self._user_selected_calibration_toml_path.hide()

    def _handle_calibrate_from_last_recording_toggled(self, checked):
        if checked:
            self._record_new_calibration_button.show()
        else:
            self._record_new_calibration_button.hide()

    def _open_load_camera_calibration_toml_dialog(self):
        # from this tutorial - https://www.youtube.com/watch?v=gg5TepTc2Jg&t=649s
        calibration_toml_path_selection = QFileDialog.getOpenFileName(
            self,
            "Select 'toml' containing camera calibration info (Note - this is the 'toml' file produced by the `anipose` calibration process)",
            str(Path.home()),
            "Camera Calibration TOML (*.toml)",
        )
        self.calibration_toml_path_str = calibration_toml_path_selection[0]
        logger.info(
            f"User selected camera calibration toml path:{self.calibration_toml_path_str}"
        )
        self._user_selected_calibration_toml_path.setText(
            self.calibration_toml_path_str
        )

    def _calibrate_from_previous_recording(self):
        print("Calibrating from previous recording")


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = CalibrationControlPanel()
    widget.show()
    sys.exit(app.exec())
