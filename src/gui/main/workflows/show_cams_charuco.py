from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QCheckBox,
)

from src.cameras.save_synchronized_videos import save_synchronized_videos
from src.gui.main.state.app_state import APP_STATE
from src.gui.main.workflows.single_camera import SingleCamera

from src.pipelines.calibration_pipeline.calibration_pipeline_orchestrator import (
    CalibrationPipelineOrchestrator,
)


class ShowCamsCharuco(QWidget):
    def __init__(self):
        super().__init__()
        # TODO: Take it in from init
        self._selected_cams = APP_STATE.selected_cameras

        self._continue_button = QPushButton("Continue")
        self._continue_button.setEnabled(False)

        self._use_previous_calibration_checkbox = (
            self._create_use_previous_calibration_checkbox()
        )

        container = QVBoxLayout()

        title_layout = QHBoxLayout()
        title = QLabel("Multi-Camera Calibration")
        title_layout.addWidget(title)

        video_stream_layout = QHBoxLayout()
        self._cam_widgets = []
        for cam_id in self._selected_cams:
            single_cam = SingleCamera(cam_id)
            single_cam.capture()
            video_stream_layout.addWidget(single_cam)
            self._cam_widgets.append(single_cam)

        container.addLayout(title_layout)
        container.addLayout(video_stream_layout)

        container.addWidget(self._use_previous_calibration_checkbox)

        # start/stop recording button layout
        record_button_layout = QHBoxLayout()
        self._start_recording_button = QPushButton("Begin Recording")
        self._stop_recording_button = QPushButton("Stop Recording")
        self._stop_recording_button.setEnabled(False)

        self._start_recording_button.clicked.connect(self._start_recording_frames)
        self._stop_recording_button.clicked.connect(self._stop_recording_frames)

        record_button_layout.addWidget(self._start_recording_button)
        record_button_layout.addWidget(self._stop_recording_button)
        container.addLayout(record_button_layout)

        container.addLayout(self._create_continue_button_container())
        container.addWidget(self._use_previous_calibration_checkbox)

        self.setLayout(container)

    @property
    def continue_button(self):
        return self._continue_button

    def _create_use_previous_calibration_checkbox(self):
        previous_calibration_checkbox = QCheckBox("Use Previous Calibration")
        previous_calibration_checkbox.setChecked(False)
        previous_calibration_checkbox.stateChanged.connect(
            self._use_previous_calibration_changed
        )
        return previous_calibration_checkbox

    def _create_continue_button_container(self):
        continue_button_layout = QHBoxLayout()
        continue_button_layout.addWidget(self._continue_button)
        return continue_button_layout

    def _use_previous_calibration_changed(self):
        self._continue_button.setEnabled(
            self._use_previous_calibration_checkbox.isChecked()
        )
        APP_STATE.use_previous_calibration = (
            self._use_previous_calibration_checkbox.isChecked()
        )

    def _start_recording_frames(self):
        self._start_recording_button.setEnabled(False)
        self._stop_recording_button.setEnabled(True)
        for cam in self._cam_widgets:
            cam.should_record_frames = True

    def _stop_recording_frames(self):
        self._stop_recording_button.setEnabled(False)
        video_recorders = []
        for cam in self._cam_widgets:
            video_recorders.append(cam.video_recorder)
            cam.quit()

        save_synchronized_videos(video_recorders, calibration_videos=True)
        self._run_anipose_calibration()
        print("Multi-camera calibration complete!")
        self._continue_button.setEnabled(True)

    def _run_anipose_calibration(self):
        print("Beginning Anipose calibration")
        calibration_orchestrator = CalibrationPipelineOrchestrator(APP_STATE.session_id)
        try:
            calibration_orchestrator.run_anipose_camera_calibration(
                charuco_square_size=39, pin_camera_0_to_origin=True
            )
        except:
            print("something failed in the anipose calibration")
            raise Exception
