import threading
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QDialog, QCheckBox, QPushButton, QLabel, QHBoxLayout, QFrame

from freemocap.gui.qt.utilities.save_and_load_gui_state import GuiState, save_gui_state
from freemocap.system.paths_and_filenames.path_getters import get_gui_state_json_path
from freemocap.system.paths_and_filenames.file_and_folder_names import SPARKLES_EMOJI_STRING


class WelcomeScreenDialog(QDialog):
    def __init__(self, gui_state: GuiState, kill_thread_event: threading.Event, parent=None) -> None:
        super().__init__(parent=parent)
        self.gui_state = gui_state
        self.kill_thread_event = kill_thread_event

        self.setMinimumSize(600, 300)

        self.setWindowTitle("Welcome to Freemocap!")

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        welcome_message = SPARKLES_EMOJI_STRING + "Welcome to Freemocap!" + SPARKLES_EMOJI_STRING

        welcome_text_label = QLabel(welcome_message)
        welcome_text_label.setWordWrap(True)
        welcome_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(welcome_text_label, 1)

        self.frame = QFrame()
        self.frame.setFrameShape(QFrame.Shape.HLine)
        self.frame.setFrameShadow(QFrame.Shadow.Sunken)
        self._layout.addWidget(self.frame)

        single_camera_doc_text = "Starting with a single camera recording is a great way to learn to use FreeMoCap.\nClick the link below for a tutorial on getting 2d data from a single camera, without any calibrating."
        single_camera_docs_label = QLabel(single_camera_doc_text)
        single_camera_docs_label.setWordWrap(True)
        self._layout.addWidget(single_camera_docs_label, 1)

        single_camera_recording_doc_link_string = '&#10132; <a href="https://freemocap.readthedocs.io/en/latest/getting_started/single_camera_recording/" style="color: #333333;"> Single camera recording tutorial</a>'
        single_camera_doc_link = QLabel(single_camera_recording_doc_link_string)
        single_camera_doc_link.setOpenExternalLinks(True)
        self._layout.addWidget(single_camera_doc_link)

        multi_camera_doc_text = "To get 3d data from FreeMoCap, you need to record with multiple cameras and calibrate them with a charuco board.\nClick the link below for a tutorial on calibrating multiple cameras."
        multi_camera_docs_label = QLabel(multi_camera_doc_text)
        multi_camera_docs_label.setWordWrap(True)
        self._layout.addWidget(multi_camera_docs_label, 1)

        multi_camera_recording_doc_link_string = '&#10132; <a href="https://freemocap.readthedocs.io/en/latest/getting_started/multi_camera_calibration/" style="color: #333333;"> Multi camera recording tutorial</a>'
        multi_camera_doc_link = QLabel(multi_camera_recording_doc_link_string)
        multi_camera_doc_link.setOpenExternalLinks(True)
        self._layout.addWidget(multi_camera_doc_link)

        sample_data_text = "You can also download sample data from the File Menu to try processing a session and see what the output looks like."
        sample_data_label = QLabel(sample_data_text)
        sample_data_label.setWordWrap(True)
        self._layout.addWidget(sample_data_label, 1)

        button_box = QHBoxLayout()

        self._dont_show_again_checkbox = QCheckBox("Don't show this again")
        self._dont_show_again_checkbox.setChecked(False)
        self._dont_show_again_checkbox.stateChanged.connect(self._dont_show_again_checkbox_changed)
        button_box.addWidget(self._dont_show_again_checkbox)

        done_button = QPushButton("Done")
        done_button.clicked.connect(self.accept)
        button_box.addWidget(done_button)

        self._layout.addLayout(button_box)

    def _dont_show_again_checkbox_changed(self) -> None:
        self.gui_state.show_welcome_screen = not self._dont_show_again_checkbox.isChecked()
        save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())
