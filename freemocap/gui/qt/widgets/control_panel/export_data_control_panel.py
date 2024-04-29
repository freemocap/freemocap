import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QVBoxLayout,
    QPushButton,
    QWidget,
    QCheckBox,
    QLabel,
    QFileDialog,
)

from freemocap.gui.qt.utilities.save_and_load_gui_state import GuiState, save_gui_state
from freemocap.system.paths_and_filenames.path_getters import get_gui_state_json_path

logger = logging.getLogger(__name__)
BLENDER_EXECUTABLE_PATH_MISSING_STRING = "BLENDER EXECUTABLE NOT FOUND"


class VisualizationControlPanel(QWidget):
    def __init__(self, gui_state: GuiState, parent=None):
        super().__init__(parent=parent)

        self._gui_state = gui_state
        self._blender_executable_path = str(self._gui_state.blender_path)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._generate_jupyter_notebook = QPushButton("Generate Jupyter Notebook")
        self._layout.addWidget(self._generate_jupyter_notebook)

        self._export_to_blender_button = QPushButton("Export to Blender")
        self.export_to_blender_button.setObjectName("export_to_blender_button")
        self._layout.addWidget(self._export_to_blender_button)

        self._open_in_blender_automatically_checkbox = QCheckBox("Open in Blender automatically")
        self._open_in_blender_automatically_checkbox.setChecked(True)

        self._layout.addWidget(QLabel("Blender Executable Path:"))

        self._blender_executable_label = QLabel(self._blender_executable_path)
        self._layout.addWidget(self._blender_executable_label)

        self._set_blender_executable_path_button = QPushButton("Choose your Blender Executable")
        self._set_blender_executable_path_button.clicked.connect(self._handle_blender_executable_button_clicked)
        self._layout.addWidget(self._set_blender_executable_path_button)
        self._layout.addStretch()

    @property
    def export_to_blender_button(self):
        return self._export_to_blender_button

    @property
    def generate_jupyter_notebook_button(self):
        return self._generate_jupyter_notebook

    @property
    def open_in_blender_automatically_box_is_checked(self):
        return self._open_in_blender_automatically_checkbox.isChecked()

    @property
    def blender_executable_path(self) -> str:
        """
        Returns the path to the Blender executable

        Returns:
            str: Path to the Blender executable
        """
        return self._blender_executable_path

    def _handle_blender_executable_button_clicked(self):
        # from this tutorial - https://www.youtube.com/watch?v=gg5TepTc2Jg&t=649s
        path_selection = QFileDialog.getOpenFileName(
            self,
            "Locate your Blender Executable",
            str(Path().home()),
            "*",
        )

        if "blender" in path_selection[0]:
            self._blender_executable_path = path_selection[0]
        elif "Blender.app" in path_selection[0]:
            self._blender_executable_path = path_selection[0] + "/Contents/MacOS/Blender"  # executable is buried on mac
        else:
            self._blender_executable_path = BLENDER_EXECUTABLE_PATH_MISSING_STRING

        logger.info(f"User selected Blender Executable path:{self._blender_executable_path}")
        self._blender_executable_label.setText(self._blender_executable_path)

        if (
            self._blender_executable_path != BLENDER_EXECUTABLE_PATH_MISSING_STRING
        ):  # don't persist missing paths across sessions
            self._gui_state.blender_path = self._blender_executable_path
            save_gui_state(gui_state=self._gui_state, file_pathstring=get_gui_state_json_path())
