import numpy as np
from PyQt6 import QtCore
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton

from src.export_stuff.blender_stuff.open_session_in_blender import (
    open_session_in_blender,
)
from src.gui.main.app_state.app_state import APP_STATE


class ProcessSessionDataPanel(QWidget):

    data_2d_done_signal = QtCore.pyqtSignal(str)
    data_3d_done_signal = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        processing_buttons_layout = QVBoxLayout()
        self._layout.addLayout(processing_buttons_layout)

        # self._process_all_button = QPushButton("Process All")
        # self._process_all_button.setEnabled(True)
        # self._process_all_button.clicked.connect(self._process_all)
        # processing_buttons_layout.addWidget(self._process_all_button)

        self._detect_2d_skeletons_button = QPushButton("Detect 2d Skeletons in Videos")
        self._detect_2d_skeletons_button.setEnabled(True)
        processing_buttons_layout.addWidget(self._detect_2d_skeletons_button)

        self._triangulate_3d_data_button = QPushButton("Triangulate 3d Data")
        self._triangulate_3d_data_button.setEnabled(True)
        processing_buttons_layout.addWidget(self._triangulate_3d_data_button)

        # self._visualize_freemocap_session_button = QPushButton(
        #     "Visualize Freemocap Session"
        # )
        # self._visualize_freemocap_session_button.setEnabled(True)
        # self._visualize_freemocap_session_button.clicked.connect(
        #     self._visualize_freemocap_session
        # )
        # processing_buttons_layout.addWidget(self._visualize_freemocap_session_button)

        self._open_in_blender_button = QPushButton("Open Session in Blender")
        self._open_in_blender_button.setEnabled(True)
        processing_buttons_layout.addWidget(self._open_in_blender_button)

    @property
    def detect_2d_skeletons_button(self):
        return self._detect_2d_skeletons_button

    @property
    def triangulate_3d_data_button(self):
        return self._triangulate_3d_data_button

    @property
    def open_in_blender_button(self):
        return self._open_in_blender_button

    def _reconstruct_3d_skeletons(self):
        pass

    #     session_orchestrator = SessionPipelineOrchestrator(
    #         session_id=APP_STATE.session_id
    #     )
    #
    #     if APP_STATE.use_previous_calibration:
    #         session_orchestrator.anipose_camera_calibration_object = (
    #             CalibrationPipelineOrchestrator().load_most_recent_anipose_calibration_toml()
    #         )
    #     else:
    #         session_orchestrator.anipose_camera_calibration_object = (
    #             CalibrationPipelineOrchestrator().load_calibration_from_session_id(
    #                 APP_STATE.session_id
    #             )
    #         )
    #
    #     session_orchestrator.mediapipe2d_numCams_numFrames_numTrackedPoints_XY = (
    #         load_mediapipe2d_data(APP_STATE.session_id)
    #     )
    #     path_to_3d_data_npy = session_orchestrator.reconstruct3d_from_2d_data_offline()
    #
    #     self.data_3d_done_signal.emit(path_to_3d_data_npy)
    #
    #     self._open_in_blender_button.setEnabled(True)

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
