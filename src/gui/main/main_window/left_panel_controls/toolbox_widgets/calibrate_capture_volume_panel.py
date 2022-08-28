from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QCheckBox,
    QFormLayout,
    QLineEdit,
)
from PyQt6.uic.properties import QtCore

from src.core_processes.capture_volume_calibration.charuco_board_detection.default_charuco_square_size import (
    default_charuco_square_size_mm,
)


class CalibrateCaptureVolumePanel(QWidget):
    def __init__(self):
        super().__init__()

        self._central_layout = QVBoxLayout()

        self._use_previous_calibration_checkbox = (
            self._create_use_previous_calibration_checkbox()
        )
        self._central_layout.addWidget(self._use_previous_calibration_checkbox)

        # start/stop recording button layout
        record_button_layout = QVBoxLayout()
        self._central_layout.addLayout(record_button_layout)

        self._start_recording_button = QPushButton("Begin Recording")
        record_button_layout.addWidget(self._start_recording_button)

        self._stop_recording_button = QPushButton("Stop Recording")
        self._stop_recording_button.setEnabled(False)
        record_button_layout.addWidget(self._stop_recording_button)

        self._charuco_square_size_form_layout = QFormLayout()
        self._charuco_square_size_line_edit_widget = QLineEdit()
        self._charuco_square_size_line_edit_widget.setText(
            str(default_charuco_square_size_mm)
        )
        self._charuco_square_size_form_layout.addRow(
            "Charuco Square Size (mm):", self._charuco_square_size_line_edit_widget
        )

        self._central_layout.addLayout(self._charuco_square_size_form_layout)

        self._calibrate_capture_volume_from_videos_button = QPushButton(
            "Calibrate Capture Volume From Videos"
        )
        self._calibrate_capture_volume_from_videos_button.setEnabled(True)
        self._central_layout.addWidget(
            self._calibrate_capture_volume_from_videos_button,
            # alignment=Qt.AlignTop,
        )

        self.setLayout(self._central_layout)

    @property
    def start_recording_button(self):
        return self._start_recording_button

    @property
    def stop_recording_button(self):
        return self._stop_recording_button

    @property
    def calibrate_capture_volume_from_videos_button(self):
        return self._calibrate_capture_volume_from_videos_button

    @property
    def use_previous_calibration_box_is_checked(self):
        return self._use_previous_calibration_checkbox.isChecked()

    @property
    def charuco_square_size(self):
        return self._charuco_square_size_line_edit_widget.text()

    def _create_use_previous_calibration_checkbox(self):
        previous_calibration_checkbox = QCheckBox("Use Previous Calibration")
        previous_calibration_checkbox.setChecked(False)

        return previous_calibration_checkbox

    def change_button_states_on_record_start(self):
        self._start_recording_button.setEnabled(False)
        self._start_recording_button.setText("Recording...")
        self._stop_recording_button.setEnabled(True)

    def change_button_states_on_record_stop(self):
        self._stop_recording_button.setEnabled(False)
        self._start_recording_button.setEnabled(True)
        self._start_recording_button.setText("Begin Recording")
        self._calibrate_capture_volume_from_videos_button.setEnabled(True)
