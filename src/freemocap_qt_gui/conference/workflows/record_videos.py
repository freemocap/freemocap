from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget, QPushButton, QCheckBox

from jon_scratch.pupil_calibration_pipeline.qt_gl_laser_skeleton_visualizer import QtGlLaserSkeletonVisualizer
from src.cameras.save_synchronized_videos import save_synchronized_videos
from src.config.home_dir import get_most_recent_session_id
from src.core_processor.mediapipe_skeleton_detector.mediapipe_skeleton_detector import MediaPipeSkeletonDetector
from src.freemocap_qt_gui.conference.app import get_qt_app
from src.freemocap_qt_gui.conference.workflows.single_camera import SingleCamera
# from src.freemocap_qt_gui.conference.workflows.visualize_session import VisualizeSkeleton
from src.freemocap_qt_gui.refactored_gui.state.app_state import APP_STATE
from src.pipelines.calibration_pipeline.calibration_pipeline_orchestrator import CalibrationPipelineOrchestrator
from src.pipelines.session_pipeline.session_pipeline_orchestrator import SessionPipelineOrchestrator, \
    load_mediapipe2d_data, load_mediapipe3d_skeleton_data


class RecordVideos(QWidget):

    def __init__(self):
        super().__init__()
        # TODO: Take it in from init
        self._selected_cams = APP_STATE.selected_cameras

        container = QVBoxLayout()

        title_layout = QHBoxLayout()
        title = QLabel("Record Session Videos")
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

        #start/stop recording button layout
        record_button_layout = QHBoxLayout()
        self._start_recording_button = QPushButton('Begin Recording')
        self._stop_recording_button = QPushButton('Stop Recording')
        self._stop_recording_button.setEnabled(False)

        self._start_recording_button.clicked.connect(self._start_recording_frames)
        self._stop_recording_button.clicked.connect(self._stop_recording_frames)

        record_button_layout.addWidget(self._start_recording_button)
        record_button_layout.addWidget(self._stop_recording_button)
        container.addLayout(record_button_layout)

        #post-recording buttons
        post_recording_button_layout = QHBoxLayout()

        self._detect_2d_skeletons_button  = QPushButton("Detect 2d Skeletons in Videos")
        self._reconstruct_3d_skeletons_button = QPushButton("Reconstruct 3d Skeletons")
        self._visualize_freemocap_session_button = QPushButton("Visualize Freemocap Session")
        self._open_in_blender_button = QPushButton("Open Session in Blender")

        self._detect_2d_skeletons_button.setEnabled(False)
        self._reconstruct_3d_skeletons_button.setEnabled(False)
        self._visualize_freemocap_session_button.setEnabled(False)

        self._detect_2d_skeletons_button.clicked.connect(self._detect_2d_skeletons)
        self._reconstruct_3d_skeletons_button.clicked.connect(self._reconstruct_3d_skeletons)
        self._visualize_freemocap_session_button.clicked.connect(self._visualize_freemocap_session)
        self._open_in_blender_button.clicked.connect(self._open_in_blender)

        self._process_automatically_checkbox = QCheckBox("Process Videos Automatically")
        container.addWidget(self._process_automatically_checkbox)

        post_recording_button_layout.addWidget( self._process_automatically_checkbox)
        post_recording_button_layout.addWidget( self._detect_2d_skeletons_button)
        post_recording_button_layout.addWidget( self._reconstruct_3d_skeletons_button)
        post_recording_button_layout.addWidget( self._visualize_freemocap_session_button)
        post_recording_button_layout.addWidget( self._open_in_blender_button)

        container.addLayout(post_recording_button_layout)

        self.setLayout(container)

    def _activate_button(self, button):
        button.setEnabled(True)
        button.setStyleSheet("background-color : #d95157")

    def _deactivate_button(self, button):
        button.setEnabled(False)
        button.setStyleSheet("background-color : #a4d6d9")

    def _start_recording_frames(self):
        self._start_recording_button.setEnabled(False)
        self._stop_recording_button.setEnabled(True)

        for cam in self._cam_widgets:
            cam.should_record_frames = True


    def _stop_recording_frames(self):
        self._stop_recording_button.setEnabled(False)
        self._detect_2d_skeletons_button.setEnabled(True)

        video_recorders = []
        for cam in self._cam_widgets:
            video_recorders.append(cam.video_recorder)
            cam.quit()
        save_synchronized_videos(video_recorders, mocap_videos=True)

        if self._process_automatically_checkbox.isChecked():
            self._detect_2d_skeletons()


    def _detect_2d_skeletons(self):
        print(f"tracking 2D mediapipe skeletons in videos from session: {APP_STATE.session_id}")
        mediapipe_skeleton_detector = MediaPipeSkeletonDetector(APP_STATE.session_id)
        mediapipe_skeleton_detector.process_session_folder()

        self._detect_2d_skeletons_button.setEnabled(False)
        self._reconstruct_3d_skeletons_button.setEnabled(True)

        if self._process_automatically_checkbox.isChecked():
            self._reconstruct_3d_skeletons()


    def _reconstruct_3d_skeletons(self):
        print(f"Reconstruct 3D Skeletons : {APP_STATE.session_id}")
        session_orchestrator = SessionPipelineOrchestrator(session_id=APP_STATE.session_id)

        if APP_STATE.use_previous_calibration:
            session_orchestrator.anipose_camera_calibration_object = CalibrationPipelineOrchestrator().load_most_recent_calibration()
        else:
            session_orchestrator.anipose_camera_calibration_object = CalibrationPipelineOrchestrator().load_calibration_from_session_id(
            APP_STATE.session_id)

        session_orchestrator.mediapipe2d_numCams_numFrames_numTrackedPoints_XY = load_mediapipe2d_data(APP_STATE.session_id)
        session_orchestrator.reconstruct3d_from_2d_data_offline()

        self._reconstruct_3d_skeletons_button.setEnabled(False)
        self._open_in_blender_button.setEnabled(True)

    def _visualize_freemocap_session(self):
        pass
        # mediapipe3d_data_payload = load_mediapipe3d_skeleton_data(APP_STATE.session_id)
        #
        # mediapipe3d_skeleton_nFrames_nTrajectories_xyz = mediapipe3d_data_payload.data3d_numFrames_numTrackedPoints_XYZ
        # mediapipe3d_skeleton_nFrames_nTrajectories_reprojectionError = mediapipe3d_data_payload.data3d_numFrames_numTrackedPoint_reprojectionError
        #
        # visualize_skeleton_dialog = VisualizeSkeleton(
        #     mediapipe_skel_fr_mar_xyz=mediapipe3d_skeleton_nFrames_nTrajectories_xyz)
        #
        # get_qt_app().quit()
        # visualize_skeleton_dialog.exec()
        # visualize_skeleton_dialog.start_animation()

    def _open_in_blender(self):
        print(f"Open in Blender : {APP_STATE.session_id}")

        pass