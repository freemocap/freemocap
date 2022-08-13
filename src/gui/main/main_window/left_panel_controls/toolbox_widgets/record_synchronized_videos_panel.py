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

        # self._process_all_push_button = QPushButton("Process All")
        # self._layout.addWidget(self._process_all_push_button)
        # post_recording_button_layout.addWidget(self._process_all)

        # post-recording buttons
        post_recording_button_layout = QVBoxLayout()
        self._layout.addLayout(post_recording_button_layout)

        self._detect_2d_skeletons_button = QPushButton("Detect 2d Skeletons in Videos")
        self._detect_2d_skeletons_button.setEnabled(True)
        self._detect_2d_skeletons_button.clicked.connect(self._detect_2d_skeletons)
        post_recording_button_layout.addWidget(self._detect_2d_skeletons_button)

        self._reconstruct_3d_skeletons_button = QPushButton("Reconstruct 3d Skeletons")
        self._reconstruct_3d_skeletons_button.setEnabled(False)
        self._reconstruct_3d_skeletons_button.clicked.connect(
            self._reconstruct_3d_skeletons
        )
        post_recording_button_layout.addWidget(self._reconstruct_3d_skeletons_button)

        self._visualize_freemocap_session_button = QPushButton(
            "Visualize Freemocap Session"
        )
        self._visualize_freemocap_session_button.setEnabled(False)
        self._visualize_freemocap_session_button.clicked.connect(
            self._visualize_freemocap_session
        )
        post_recording_button_layout.addWidget(self._visualize_freemocap_session_button)

        self._open_in_blender_button = QPushButton("Open Session in Blender")
        self._open_in_blender_button.clicked.connect(
            self._create_blender_scene_from_session_data
        )
        self._open_in_blender_button.setEnabled(False)
        post_recording_button_layout.addWidget(self._open_in_blender_button)

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

    def _detect_2d_skeletons(self):
        print(
            f"tracking 2D mediapipe skeletons in videos from session: {APP_STATE.session_id}"
        )
        mediapipe_skeleton_detector = MediaPipeSkeletonDetector()
        mediapipe_skeleton_detector.process_session_folder(
            get_synchronized_videos_folder_path(APP_STATE.session_id)
        )

        self._detect_2d_skeletons_button.setEnabled(False)
        self._reconstruct_3d_skeletons_button.setEnabled(True)

    def _reconstruct_3d_skeletons(self):
        print(f"Reconstruct 3D Skeletons : {APP_STATE.session_id}")
        session_orchestrator = SessionPipelineOrchestrator(
            session_id=APP_STATE.session_id
        )

        if APP_STATE.use_previous_calibration:
            session_orchestrator.anipose_camera_calibration_object = (
                CalibrationPipelineOrchestrator().load_most_recent_calibration()
            )
        else:
            session_orchestrator.anipose_camera_calibration_object = (
                CalibrationPipelineOrchestrator().load_calibration_from_session_id(
                    APP_STATE.session_id
                )
            )

        session_orchestrator.mediapipe2d_numCams_numFrames_numTrackedPoints_XY = (
            load_mediapipe2d_data(APP_STATE.session_id)
        )
        session_orchestrator.reconstruct3d_from_2d_data_offline()

        self._reconstruct_3d_skeletons_button.setEnabled(False)
        self._open_in_blender_button.setEnabled(True)

    def _visualize_freemocap_session(self):
        pass
        # mediapipe3d_data_payload = load_mediapipe3d_skeleton_data(APP_STATE.session_id)
        #
        # mediapipe3d_skeleton_nFrames_nTrajectories_xyz =
        # mediapipe3d_data_payload.data3d_numFrames_numTrackedPoints_XYZ
        # mediapipe3d_skeleton_nFrames_nTrajectories_reprojectionError =
        # mediapipe3d_data_payload.data3d_numFrames_numTrackedPoint_reprojectionError
        #
        # visualize_skeleton_dialog = VisualizeSkeleton(
        #     mediapipe_skel_fr_mar_xyz=mediapipe3d_skeleton_nFrames_nTrajectories_xyz)
        #
        # get_qt_app().quit()
        # visualize_skeleton_dialog.exec()
        # visualize_skeleton_dialog.start_animation()

    def _create_blender_scene_from_session_data(self):
        print(f"Open in Blender : {APP_STATE.session_id}")
        open_session_in_blender(APP_STATE.session_id)
