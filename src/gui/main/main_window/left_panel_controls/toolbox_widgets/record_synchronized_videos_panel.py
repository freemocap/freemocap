from PyQt6.QtWidgets import (
    QPushButton,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)


class RecordSynchronizedVideosPanel(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._layout.addStretch()

        self._start_recording_button = QPushButton("Begin Recording")
        self._layout.addWidget(self._start_recording_button)

        self._stop_recording_button = QPushButton("Stop Recording")
        self._stop_recording_button.setEnabled(False)
        self._layout.addWidget(self._stop_recording_button)

        self._process_automatically_checkbox = QCheckBox(
            "Process Recording Automatically"
        )
        self._process_automatically_checkbox.setChecked(True)
        self._layout.addWidget(self._process_automatically_checkbox)

        self._open_in_blender_automatically_checkbox = QCheckBox(
            "Open in Blender automatically"
        )
        self._open_in_blender_automatically_checkbox.setChecked(True)
        self._layout.addWidget(self._open_in_blender_automatically_checkbox)
        self._layout.addStretch()

    @property
    def open_in_blender_automatically_checkbox(self):
        return self._open_in_blender_automatically_checkbox

    @property
    def process_recording_automatically_checkbox(self):
        return self._process_automatically_checkbox

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
