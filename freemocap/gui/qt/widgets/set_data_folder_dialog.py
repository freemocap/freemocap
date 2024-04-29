from pathlib import Path
import threading

from PySide6.QtWidgets import QVBoxLayout, QDialog, QPushButton, QLabel, QHBoxLayout, QFileDialog

from freemocap.gui.qt.utilities.save_and_load_gui_state import GuiState, save_gui_state
from freemocap.system.paths_and_filenames.path_getters import get_gui_state_json_path


class SetDataFolderDialog(QDialog):
    def __init__(self, gui_state: GuiState, kill_thread_event: threading.Event, parent=None) -> None:
        super().__init__(parent=parent)
        self.gui_state = gui_state
        self.kill_thread_event = kill_thread_event

        self._initUI()

    def _initUI(self) -> None:
        self.setMinimumSize(500, 200)

        self.setWindowTitle("Set Freemocap Data Folder")

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._title_message_label = QLabel(f"Freemocap Data Folder: {self.gui_state.freemocap_data_folder_path}")
        self._title_message_label.setWordWrap(True)
        self._layout.addWidget(self._title_message_label)

        self._change_data_folder_button = QPushButton("Change Folder Location")
        self._change_data_folder_button.clicked.connect(self._change_data_folder)
        self._layout.addWidget(self._change_data_folder_button)

        self._reboot_warning_label = QLabel("Changing the freemocap data folder will reboot the GUI.")
        self._layout.addWidget(self._reboot_warning_label)

        button_box = QHBoxLayout()

        _cancel_button = QPushButton("Cancel")
        _cancel_button.clicked.connect(self.reject)
        button_box.addWidget(_cancel_button)

        self._done_button = QPushButton("Save and Reboot")
        self._done_button.clicked.connect(self._save_and_accept)
        button_box.addWidget(self._done_button)

        self._layout.addLayout(button_box)

    def _change_data_folder(self) -> None:
        self.new_folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select New Data Folder",
            str(self.gui_state.freemocap_data_folder_path),
            QFileDialog.ShowDirsOnly,
        )
        self._title_message_label.setText(f"Freemocap Data Folder: {self.new_folder_path}")

        if self.new_folder_path == "":
            self._done_button.setEnabled(False)
        else:
            self._done_button.setEnabled(True)

    def _save_and_accept(self) -> None:
        if self.new_folder_path is not None:
            freemocap_data_folder_path = Path(self.new_folder_path)
            self.gui_state.freemocap_data_folder_path = str(freemocap_data_folder_path)
            save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())

            self.accept()
