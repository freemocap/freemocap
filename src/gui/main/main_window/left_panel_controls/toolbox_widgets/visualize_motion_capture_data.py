from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
)


class VisualizeMotionCaptureDataPanel(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()

        self._load_session_data_button = QPushButton(
            "Load Session Data",
        )
        self._load_session_data_button.setEnabled(True)
        self._layout.addWidget(self._load_session_data_button)
        self._load_session_data_button.clicked.connect(
            self._handle_load_session_data_button_clicked,
        )

        self._play_button = QPushButton("Play")
        self._play_button.setEnabled(False)
        self._layout.addWidget(self._play_button)
        self._play_button.hide()
        self._play_button.clicked.connect(self._handle_play_button_clicked)

        self._pause_button = QPushButton("Pause")
        self._pause_button.setEnabled(False)
        self._layout.addWidget(self._pause_button)
        self._pause_button.hide()
        self._pause_button.clicked.connect(self._handle_pause_button_clicked)

        self._layout.addStretch()

        self.setLayout(self._layout)

        self._should_pause_playback_bool = False

    @property
    def load_session_data_button(self):
        return self._load_session_data_button

    @property
    def play_button(self):
        return self._play_button

    @property
    def pause_button(self):
        return self._pause_button

    @property
    def should_pause_playback_bool(self):
        return self._should_pause_playback_bool

    def _handle_load_session_data_button_clicked(self):
        self._load_session_data_button.setEnabled(False)
        self._play_button.setEnabled(False)
        self._pause_button.setEnabled(True)

    def _handle_play_button_clicked(self):
        self._should_pause_playback_bool = False
        self._play_button.setEnabled(False)
        self._pause_button.setEnabled(True)

    def _handle_pause_button_clicked(self):
        self._should_pause_playback_bool = True
        self._play_button.setEnabled(True)
        self._pause_button.setEnabled(False)
