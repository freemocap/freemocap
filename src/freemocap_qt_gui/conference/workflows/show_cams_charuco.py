from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.freemocap_qt_gui.conference.workflows.single_camera import SingleCamera
from src.freemocap_qt_gui.refactored_gui.state.app_state import APP_STATE


class ShowCamsCharuco(QWidget):

    def __init__(self):
        super().__init__()
        # TODO: Take it in from init
        self._selected_cams = APP_STATE.selected_cameras

        container = QVBoxLayout()

        title_layout = QHBoxLayout()
        title = QLabel("Multi-Camera Calibration")
        title_layout.addWidget(title)

        video_stream_layout = QHBoxLayout()
        cam_widgets = []
        for cam_id in self._selected_cams:
            single_cam = SingleCamera(cam_id)
            single_cam.capture()
            video_stream_layout.addWidget(single_cam)
            cam_widgets.append(single_cam)

        container.addLayout(title_layout)
        container.addLayout(video_stream_layout)

        self.setLayout(container)

