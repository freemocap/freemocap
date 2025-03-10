import threading

from PySide6.QtWidgets import QVBoxLayout, QDialog, QCheckBox, QPushButton, QLabel, QHBoxLayout

from freemocap.gui.qt.utilities.save_and_load_gui_state import GuiState, save_gui_state
from freemocap.system.paths_and_filenames.path_getters import get_gui_state_json_path


class DataWarningDialog(QDialog):
    def __init__(self, gui_state: GuiState, kill_thread_event: threading.Event, parent=None) -> None:
        super().__init__(parent=parent)
        self.gui_state = gui_state
        self.kill_thread_event = kill_thread_event

        self.setMinimumSize(600, 300)

        self.setWindowTitle("Data Quality Warning")

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        warning_test = (
            "Whoops! There was a data quality regression because of a bug that made us skip the butterworth step since version 1.4.7 \n"
            "We recommend re-processing any imoprtant data you have collected in that period.\n"
            "We are working on automated diagnostic steps to help us detect regressions in data quality as soon as possible."
        )
        warning_text_label = QLabel(warning_test)
        warning_text_label.setWordWrap(True)
        self._layout.addWidget(warning_text_label, 1)

        diagnostic_pr_link_string = f'&#10132; <a href="https://github.com/freemocap/freemocap/pull/676" style="color: #333333;">Pull Request: Improved Data Diagnostics</a>'
        diagnostic_pr_link = QLabel(diagnostic_pr_link_string)
        diagnostic_pr_link.setOpenExternalLinks(True)
        self._layout.addWidget(diagnostic_pr_link)

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
        self.gui_state.show_data_quality_warning = not self._dont_show_again_checkbox.isChecked()
        save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())
