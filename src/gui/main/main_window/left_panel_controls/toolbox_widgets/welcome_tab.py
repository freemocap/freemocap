from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
)


class SelectWorkflowScreen(QWidget):
    def __init__(self):
        super().__init__()

        container_layout = QVBoxLayout()

        self._start_new_session_button = QPushButton("&Start New Session")
        container_layout.addWidget(self._start_new_session_button)

        self._load_previous_session_button = QPushButton(
            "TO DO - &Load Previous Session"
        )
        self._load_previous_session_button.setEnabled(False)
        container_layout.addWidget(self._load_previous_session_button)

        self._import_external_videos = QPushButton("TO DO - &Import External Videos")
        self._import_external_videos.setEnabled(False)
        container_layout.addWidget(self._import_external_videos)

        self.setLayout(container_layout)

    @property
    def start_new_session_button(self):
        return self._start_new_session_button
