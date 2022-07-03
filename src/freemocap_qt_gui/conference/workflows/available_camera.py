from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QWidget


class AvailableCamera(QWidget):

    def __init__(self, camera_name: str = "0"):
        super().__init__()
        self._camera_name = camera_name

        name_layout = QHBoxLayout()
        name_layout.setSpacing(20)
        name_layout.addWidget(self._create_checkbox())
        name_layout.addWidget(self._create_title())
        self._preview_button = self._create_preview_button()
        name_layout.addWidget(self._preview_button)

        self.setLayout(name_layout)

    @property
    def preview(self):
        return self._preview_button

    def _create_title(self):
        camera_title = QLabel(f"Camera {self._camera_name}")
        return camera_title

    def _create_checkbox(self):
        show_hide_checkbox = QCheckBox()
        show_hide_checkbox.setChecked(True)
        return show_hide_checkbox

    def _create_preview_button(self):
        preview = QPushButton("Preview")
        return preview
