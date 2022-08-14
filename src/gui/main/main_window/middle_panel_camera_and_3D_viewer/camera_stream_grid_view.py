import numpy as np
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QGridLayout, QVBoxLayout

from src.cameras.save_synchronized_videos import save_synchronized_videos
from src.gui.main.app_state.app_state import APP_STATE
from src.gui.main.custom_widgets.single_camera_widget import SingleCameraWidget
from src.gui.main.qt_utils.clear_layout import clear_layout


class CameraStreamGridView(QWidget):
    cameras_connected_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._camera_widgets = []

        self._camera_stream_layout = QVBoxLayout()
        self.setLayout(self._camera_stream_layout)

    @property
    def video_recorders(self):
        return [cam.video_recorder for cam in self._camera_widgets]

    def connect_to_camera_streams(self):
        for webcam_id in APP_STATE.selected_cameras:
            single_cam_widget = SingleCameraWidget(webcam_id)
            single_cam_widget.capture()
            self._camera_stream_layout.addWidget(single_cam_widget)
            self._camera_widgets.append(single_cam_widget)

        self.cameras_connected_signal.emit()

    def close_all_camera_streams(self):
        for camera_widget in self._camera_widgets:
            camera_widget.quit()

    def start_recording_videos(self):
        for camera_widget in self._camera_widgets:
            camera_widget.start_recording()

    def stop_recording_videos(self):
        for camera_widget in self._camera_widgets:
            camera_widget.stop_recording()

    def save_synchronized_videos(self):
        video_recorders = []
        for cam in self._camera_widgets:
            video_recorders.append(cam.video_recorder)

    def reconnect_to_cameras(self):
        self._camera_widgets = []
        clear_layout(self._camera_stream_layout)
        self.connect_to_camera_streams()
