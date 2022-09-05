import logging

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QCheckBox,
    QFormLayout,
    QLineEdit,
)

from src.core_processes.capture_volume_calibration.charuco_board_detection.default_charuco_square_size import (
    default_charuco_square_size_mm,
)

logger = logging.getLogger(__name__)


class CalibrateCaptureVolumePanel(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.addStretch()

        self._use_previous_calibration_checkbox = (
            self._create_use_previous_calibration_checkbox()
        )
        self._layout.addWidget(self._use_previous_calibration_checkbox)

        # start/stop recording button layout
        record_button_layout = QVBoxLayout()
        self._layout.addLayout(record_button_layout)

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

        self._layout.addLayout(self._charuco_square_size_form_layout)

        self._calibrate_capture_volume_from_videos_button = QPushButton(
            "Calibrate Capture Volume From Videos"
        )
        self._calibrate_capture_volume_from_videos_button.setEnabled(False)
        self._layout.addWidget(
            self._calibrate_capture_volume_from_videos_button,
        )

        self._process_automatically_checkbox = QCheckBox("Process Automatically")
        self._process_automatically_checkbox.setChecked(True)
        self._process_automatically_checkbox.stateChanged.connect(
            self._enable_or_disable_calibrate_from_videos_button
        )
        self._layout.addWidget(self._process_automatically_checkbox)

        self._layout.addStretch()

    @property
    def process_recording_automatically_checkbox(self):
        return self._process_automatically_checkbox

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
    def charuco_square_size(self) -> float:
        return float(self._charuco_square_size_line_edit_widget.text())

    def _create_use_previous_calibration_checkbox(self):
        previous_calibration_checkbox = QCheckBox("Use Previous Calibration")
        previous_calibration_checkbox.setChecked(False)

        return previous_calibration_checkbox

    def _enable_or_disable_calibrate_from_videos_button(self):
        logger.debug('Process calibration videos automatically checkbox state changed')
        if self._process_automatically_checkbox.isChecked():
            self._calibrate_capture_volume_from_videos_button.setEnabled(False)
        else:
            self._calibrate_capture_volume_from_videos_button.setEnabled(True)


    def change_button_states_on_record_start(self):
        self._start_recording_button.setEnabled(False)
        self._start_recording_button.setText("Recording...")
        self._stop_recording_button.setEnabled(True)

    def change_button_states_on_record_stop(self):
        self._stop_recording_button.setEnabled(False)
        self._start_recording_button.setEnabled(True)
        self._start_recording_button.setText("Begin Recording")
        self._calibrate_capture_volume_from_videos_button.setEnabled(True)
