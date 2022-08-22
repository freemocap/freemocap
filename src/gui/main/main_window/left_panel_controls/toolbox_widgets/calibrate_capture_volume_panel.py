from typing import Dict

import toml
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QCheckBox,
    QFormLayout,
    QLineEdit,
)
from pyqtgraph import DataTreeWidget

from src.cameras.save_synchronized_videos import save_synchronized_videos
from src.config.home_dir import get_session_calibration_toml_file_path
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.styled_widgets.page_title import PageTitle
from src.pipelines.calibration_pipeline.calibration_pipeline_orchestrator import (
    CalibrationPipelineOrchestrator,
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
        self._charuco_square_size_line_edit_widget.setText(str(39))
        self._charuco_square_size_form_layout.addRow(
            "Charuco Square Size (mm):", self._charuco_square_size_line_edit_widget
        )
        self._central_layout.addLayout(self._charuco_square_size_form_layout)

        self._calibrate_from_videos_button = QPushButton("Calibrate From Videos")
        self._calibrate_from_videos_button.clicked.connect(
            self._run_anipose_calibration
        )
        self._calibrate_from_videos_button.setEnabled(False)
        self._central_layout.addWidget(self._calibrate_from_videos_button)

        self.setLayout(self._central_layout)

    @property
    def start_recording_button(self):
        return self._start_recording_button

    @property
    def stop_recording_button(self):
        return self._stop_recording_button

    def _create_use_previous_calibration_checkbox(self):
        previous_calibration_checkbox = QCheckBox("Use Previous Calibration")
        previous_calibration_checkbox.setChecked(False)
        previous_calibration_checkbox.stateChanged.connect(
            self._use_previous_calibration_changed
        )
        return previous_calibration_checkbox

    def _use_previous_calibration_changed(self):
        self._start_recording_button.setEnabled(
            self._use_previous_calibration_checkbox.isChecked()
        )
        APP_STATE.use_previous_calibration = (
            self._use_previous_calibration_checkbox.isChecked()
        )

    def change_button_states_on_record_start(self):
        self._start_recording_button.setEnabled(False)
        self._start_recording_button.setText("Recording...")
        self._stop_recording_button.setEnabled(True)

    def change_button_states_on_record_stop(self):
        self._stop_recording_button.setEnabled(False)
        self._start_recording_button.setEnabled(True)
        self._start_recording_button.setText("Begin Recording")
        self._calibrate_from_videos_button.setEnabled(True)

    def _run_anipose_calibration(self):
        print("Beginning Anipose calibration")
        calibration_orchestrator = CalibrationPipelineOrchestrator(APP_STATE.session_id)
        try:
            calibration_orchestrator.run_anipose_camera_calibration(
                charuco_square_size=int(
                    self._charuco_square_size_line_edit_widget.text()
                ),
                pin_camera_0_to_origin=True,
            )
        except:
            print("something failed in the anipose calibration")
            raise Exception
        print("Anipose calibration complete")
        self._create_calibration_toml_data_tree_widget()

    def _create_calibration_toml_data_tree_widget(self):
        calibration_toml_file_path = get_session_calibration_toml_file_path(
            APP_STATE.session_id
        )
        calibration_dictionary = toml.load(calibration_toml_file_path)
        self.calibration_data_tree_widget = DataTreeWidget(data=calibration_dictionary)
        self.calibration_data_tree_widget.show()
        self._central_layout.addWidget((self.calibration_data_tree_widget))
