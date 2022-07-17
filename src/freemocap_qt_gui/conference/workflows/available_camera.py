from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QWidget


class AvailableCamera(QWidget):

    def __init__(self, webcam_id: str = "0"):
        super().__init__()
        self._webcam_id = webcam_id

        name_layout = QHBoxLayout()
        name_layout.setSpacing(20)
        self._show_cam_checkbox = self._create_checkbox()
        name_layout.addWidget(self._create_checkbox())
        name_layout.addWidget(self._create_title())
        self._preview_button = self._create_preview_button()
        name_layout.addWidget(self._preview_button)

        self.setLayout(name_layout)

    @property
    def preview(self):
        return self._preview_button

    @property
    def webcam_id(self):
        return self._webcam_id

    @property
    def show_cam_checkbox(self):
        return self._show_cam_checkbox

    def _create_title(self):
        camera_title = QLabel(f"Camera {self._webcam_id}")
        return camera_title

    def _create_checkbox(self):
        show_hide_checkbox = QCheckBox()
        show_hide_checkbox.setChecked(True)
        show_hide_checkbox.stateChanged.connect(self._state_changed)
        return show_hide_checkbox

    def _create_preview_button(self):
        preview = QPushButton("Preview")
        return preview

    def _state_changed(self, state):
        if self._show_cam_checkbox.isChecked() == bool(state):
            return
        self._show_cam_checkbox.setChecked(state)
        checked = self._show_cam_checkbox.isChecked()
