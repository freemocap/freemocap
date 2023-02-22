from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QPushButton, QRadioButton, QWidget, QCheckBox


class VisualizationControlPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
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

    @property
    def export_to_blender_button(self):
        return self._export_to_blender_button

    @property
    def open_in_blender_automatically_box_is_checked(self):
        return self._open_in_blender_automatically_checkbox.isChecked()

    def get_user_selected_method_string(self):
        if self._use_default_method_radio_button.isChecked():
            return "megascript_take2"

        if self._use_legacy_method_radio_button.isChecked():
            return "alpha_megascript"

        if self._use_cgtinker_method_radio_button.isChecked():
            return "cgtinker"
