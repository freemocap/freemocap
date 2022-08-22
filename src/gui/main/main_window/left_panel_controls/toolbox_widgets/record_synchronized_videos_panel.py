from PyQt6.QtWidgets import (
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.config.home_dir import get_synchronized_videos_folder_path
from src.core_processor.mediapipe_skeleton_detector.mediapipe_skeleton_detector import (
    MediaPipeSkeletonDetector,
)
from src.gui.main.app_state.app_state import APP_STATE
from src.export_stuff.blender_stuff.open_session_in_blender import (
    open_session_in_blender,
)
from src.pipelines.calibration_pipeline.calibration_pipeline_orchestrator import (
    CalibrationPipelineOrchestrator,
)
from src.pipelines.session_pipeline.session_pipeline_orchestrator import (
    SessionPipelineOrchestrator,
    load_mediapipe2d_data,
)


class RecordSynchronizedVideosPanel(QWidget):
    def __init__(self):
        super().__init__()
        # TODO: Take it in from init
        self._selected_cams = APP_STATE.selected_cameras

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        # start/stop recording button layout
        record_button_layout = QVBoxLayout()
        self._layout.addLayout(record_button_layout)

        self._start_recording_button = QPushButton("Begin Recording")
        record_button_layout.addWidget(self._start_recording_button)

        self._stop_recording_button = QPushButton("Stop Recording")
        self._stop_recording_button.setEnabled(False)
        record_button_layout.addWidget(self._stop_recording_button)

    @property
    def start_recording_button(self):
        return self._start_recording_button

    @property
    def stop_recording_button(self):
        return self._stop_recording_button

    def change_button_states_on_record_start(self):
        self._start_recording_button.setEnabled(False)
        self._start_recording_button.setText("Recording...")
        self._stop_recording_button.setEnabled(True)

    def change_button_states_on_record_stop(self):
        self._stop_recording_button.setEnabled(False)
        self._start_recording_button.setEnabled(True)
        self._start_recording_button.setText("Begin Recording")
