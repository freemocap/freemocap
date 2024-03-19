import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QDialog, QCheckBox, QPushButton, QLabel, QHBoxLayout, QFrame

from freemocap.gui.qt.utilities.save_and_load_gui_state import GuiState, save_gui_state
from freemocap.system.paths_and_filenames.path_getters import get_gui_state_json_path


class SettingsDialog(QDialog):
    def __init__(self, gui_state: GuiState, kill_thread_event: threading.Event, parent=None) -> None:
        super().__init__(parent=parent)
        self.gui_state = gui_state
        self.kill_thread_event = kill_thread_event

        self.setMinimumSize(600, 300)

        self.setWindowTitle("Freemocap Settings")

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self.title_message_label = QLabel("Settings Will Be Here")
        self._layout.addWidget(self.title_message_label)

        self.frame = QFrame()
        self.frame.setFrameShape(QFrame.Shape.HLine)
        self.frame.setFrameShadow(QFrame.Shadow.Sunken)
        self._layout.addWidget(self.frame)

        button_box = QHBoxLayout()

        done_button = QPushButton("Done")
        done_button.clicked.connect(self.accept)
        button_box.addWidget(done_button)

        self._layout.addLayout(button_box)

    def _dont_show_again_checkbox_changed(self) -> None:
        self.gui_state.show_welcome_screen = not self._dont_show_again_checkbox.isChecked()
        save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())
