import logging
from pathlib import Path
from typing import Union

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QPushButton, QRadioButton, QWidget, QCheckBox, QLabel, QFileDialog

logger = logging.getLogger(__name__)


class VisualizationControlPanel(QWidget):
    def __init__(self, blender_executable: Union[str, Path], parent=None):
        super().__init__(parent=parent)

        self._blender_executable = str(blender_executable)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        groupbox = QGroupBox("Export to Blender", parent=self)
        self._layout.addWidget(groupbox)
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        groupbox.setLayout(vbox)

        self._export_to_blender_button = QPushButton("Export to Blender")
        groupbox.layout().addWidget(self._export_to_blender_button)

        self._open_in_blender_automatically_checkbox = QCheckBox("Open in Blender automatically")
        self._open_in_blender_automatically_checkbox.setChecked(True)
        groupbox.layout().addWidget(self._open_in_blender_automatically_checkbox)

        self._use_default_method_radio_button = QRadioButton("Use default method (Recommended)")
        self._use_default_method_radio_button.setChecked(True)
        groupbox.layout().addWidget(self._use_default_method_radio_button)

        self._use_legacy_method_radio_button = QRadioButton("Use legacy method")
        groupbox.layout().addWidget(self._use_legacy_method_radio_button)

        self._use_cgtinker_method_radio_button = QRadioButton("Use @cgtinker method (Work in progress)")
        groupbox.layout().addWidget(self._use_cgtinker_method_radio_button)


        self._layout.addWidget(QLabel("Blender Executable Path:"))

        self._blender_executable_label = QLabel(self._blender_executable)
        self._layout.addWidget(self._blender_executable_label)

        self._set_blender_executable_path_button = QPushButton("Get Blender Path")
        self._set_blender_executable_path_button.clicked.connect(self._handle_blender_executable_button_clicked)
        self._layout.addWidget(self._set_blender_executable_path_button)
        self._layout.addStretch()

    @property
    def export_to_blender_button(self):
        return self._export_to_blender_button

    @property
    def open_in_blender_automatically_box_is_checked(self):
        return self._open_in_blender_automatically_checkbox.isChecked()

    @property
    def blender_executable(self) -> str:
        return self._blender_executable

    def get_user_selected_method_string(self):
        if self._use_default_method_radio_button.isChecked():
            return "megascript_take2"

        if self._use_legacy_method_radio_button.isChecked():
            return "alpha_megascript"

        if self._use_cgtinker_method_radio_button.isChecked():
            return "cgtinker"


    def _handle_blender_executable_button_clicked(self):
        # from this tutorial - https://www.youtube.com/watch?v=gg5TepTc2Jg&t=649s
        path_selection = QFileDialog.getOpenFileName(
            self,
            "Locate your Blender Executable",
            str(Path().home()),
            "*.*",
        )
        self._blender_executable = path_selection[0]
        logger.info(f"User selected Blender Executable path:{self._blender_executable}")
        self._blender_executable_label.setText(self._blender_executable)
