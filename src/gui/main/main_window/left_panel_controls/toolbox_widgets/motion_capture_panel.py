from PyQt6.QtCore import QLine, Qt
from PyQt6.QtWidgets import (
    QPushButton,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QLabel,
)

from src.gui.main.main_window.left_panel_controls.toolbox_widgets.process_session_data_panel import (
    ProcessSessionDataPanel,
)
from src.gui.main.main_window.left_panel_controls.toolbox_widgets.visualize_motion_capture_data import (
    VisualizeMotionCaptureDataPanel,
)
from src.gui.main.style_stuff.styled_widgets.panel_section_title import (
    PanelSectionTitle,
)


class MotionCapturePanel(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._layout.addStretch()
        self._layout.addWidget(
            PanelSectionTitle("Record Synchronized Videos"), alignment=Qt.AlignCenter
        )
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

        self._layout.addWidget(QLabel("___"), alignment=Qt.AlignCenter)

        process_videos_section_title = PanelSectionTitle("Process Videos")
        self._layout.addWidget(process_videos_section_title, alignment=Qt.AlignCenter)
        process_videos_section_title.setToolTip(
            "TODO: \n"
            + "- Convert this mess of buttons into a 'Parameter Tree' like the one in the 'Camera Setup' panel (see `src/core_processes/batch_processes/process_session_folder.py`)\n\n"
            + "- Add method to check what's in the `session_folder` and only enable the appropriate buttons"
        )

        self._process_session_data_panel = ProcessSessionDataPanel()

        self._layout.addWidget(self._process_session_data_panel)

        self._layout.addWidget(QLabel("___"), alignment=Qt.AlignCenter)

        self._layout.addWidget(
            PanelSectionTitle("Visualize Data"), alignment=Qt.AlignCenter
        )
        self._visualize_motion_capture_data_panel = VisualizeMotionCaptureDataPanel()

        self._layout.addWidget(self._visualize_motion_capture_data_panel)
        self._layout.addStretch()

    @property
    def process_session_data_panel(self):
        return self._process_session_data_panel

    @property
    def visualize_session_data_panel(self):
        return self._visualize_motion_capture_data_panel

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
