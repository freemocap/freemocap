import logging
from pathlib import Path

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

from freemocap.qt_gui.workers.anipose_calibration_thread_worker import (
    AniposeCalibrationThreadWorker,
)
from old_src.core_processes.capture_volume_calibration.charuco_board_detection.default_charuco_square_size import (
    default_charuco_square_size_mm,
)

logger = logging.getLogger(__name__)


class CalibrationControlPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._radio_button_layout = self._create_radio_button_layout()
        self._radio_button_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.addLayout(self._radio_button_layout)
        self._layout.addStretch()

    def _create_radio_button_layout(self):
        radio_button_layout = QVBoxLayout()

        self._add_use_most_recent_calibration_radio_button(radio_button_layout)

        self._add_load_calibration_from_file_radio_button(radio_button_layout)

        self._add_calibrate_from_last_recording_radio_button(radio_button_layout)

        return radio_button_layout

    def _add_use_most_recent_calibration_radio_button(
        self, radio_button_layout: QVBoxLayout
    ):
        self._use_most_recent_calibration_radio_button = QRadioButton(
            "Use most recent calibration"
        )
        self._use_most_recent_calibration_radio_button.setChecked(True)
        self._use_most_recent_calibration_radio_button.toggled.connect(
            self._handle_use_most_recent_calibration_toggled
        )
        radio_button_layout.addWidget(self._use_most_recent_calibration_radio_button)

        self._most_recent_calibration_path = QLabel("--Most recent calibration path--")
        radio_button_layout.addWidget(self._most_recent_calibration_path)

    def _add_load_calibration_from_file_radio_button(
        self, radio_button_layout: QVBoxLayout
    ):
        self._load_calibration_from_file_radio_button = QRadioButton(
            "Load calibration from file"
        )
        self._load_calibration_from_file_radio_button.toggled.connect(
            self._handle_load_calibration_from_file_toggled
        )
        radio_button_layout.addWidget(self._load_calibration_from_file_radio_button)

        self._load_calibration_toml_dialog_button = QPushButton(
            "Load Camera Calibration TOML..."
        )
        self._load_calibration_toml_dialog_button.setStyleSheet("font-size: 16px")
        self._load_calibration_toml_dialog_button.clicked.connect(
            self._open_load_camera_calibration_toml_dialog
        )
        radio_button_layout.addWidget(self._load_calibration_toml_dialog_button)
        self._load_calibration_toml_dialog_button.hide()

        self._user_selected_calibration_toml_path = QLabel("--Calibration TOML path--")
        radio_button_layout.addWidget(self._user_selected_calibration_toml_path)
        self._user_selected_calibration_toml_path.hide()

    def _add_calibrate_from_last_recording_radio_button(
        self, radio_button_layout: QVBoxLayout
    ):
        self._record_new_calibration_radio_button = QRadioButton(
            "Calibrate from last recording"
        )
        self._record_new_calibration_radio_button.toggled.connect(
            self._handle_calibrate_from_last_recording_toggled
        )
        radio_button_layout.addWidget(self._record_new_calibration_radio_button)

        self._calibrate_from_last_recording_button = QPushButton(
            "Calibrate from last recording"
        )
        self._calibrate_from_last_recording_button.setStyleSheet("font-size: 16px")
        self._calibrate_from_last_recording_button.clicked.connect(
            self._calibrate_from_previous_recording
        )
        radio_button_layout.addWidget(self._calibrate_from_last_recording_button)
        self._calibrate_from_last_recording_button.hide()

        self._charuco_square_size_form_layout = (
            self._create_charuco_square_size_form_layout()
        )
        radio_button_layout.addLayout(self._charuco_square_size_form_layout)
        self._set_charuco_square_size_form_layout_visibility(False)

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
            self._calibrate_from_last_recording_button.show()
            self._set_charuco_square_size_form_layout_visibility(True)
        else:
            self._calibrate_from_last_recording_button.hide()
            self._set_charuco_square_size_form_layout_visibility(False)

    def _set_charuco_square_size_form_layout_visibility(self, visible):
        label_index = self._charuco_square_size_form_layout.indexOf(
            self._charuco_square_size_label
        )
        line_edit_index = self._charuco_square_size_form_layout.indexOf(
            self._charuco_square_size_line_edit
        )
        if visible:
            self._charuco_square_size_form_layout.itemAt(label_index).widget().show()
            self._charuco_square_size_form_layout.itemAt(
                line_edit_index
            ).widget().show()
        else:
            self._charuco_square_size_form_layout.itemAt(label_index).widget().hide()
            self._charuco_square_size_form_layout.itemAt(
                line_edit_index
            ).widget().hide()

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

    def _create_charuco_square_size_form_layout(self):
        charuco_square_size_form_layout = QFormLayout()
        self._charuco_square_size_line_edit = QLineEdit()
        self._charuco_square_size_label = QLabel("Charuco square size (mm)")
        self._charuco_square_size_line_edit.setText(str(default_charuco_square_size_mm))
        self._charuco_square_size_line_edit.setToolTip(
            "The length of one of the edges of the black squares in the calibration board in mm"
        )
        charuco_square_size_form_layout.addRow(
            self._charuco_square_size_label, self._charuco_square_size_line_edit
        )
        return charuco_square_size_form_layout

    def _calibrate_from_previous_recording(self):
        print("Calibrating from previous recording")

        self._anipose_calibration_frame_worker = AniposeCalibrationThreadWorker(
            charuco_square_size_mm=float(self._charuco_square_size_line_edit.text())
        )


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = CalibrationControlPanel()
    widget.show()
    sys.exit(app.exec())
