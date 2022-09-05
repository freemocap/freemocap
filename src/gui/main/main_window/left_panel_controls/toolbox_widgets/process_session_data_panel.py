import numpy as np
from PyQt6 import QtCore
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QCheckBox,
    QFormLayout,
    QLineEdit,
)

from src.core_processes.mediapipe_2d_skeleton_detector.mediapipe_default_settings import (
    default_mediapipe_confidence_threshold,
)

from src.gui.main.tool_tips.tool_tips import mediapipe_confidence_cutoff_tool_tip_str


class ProcessSessionDataPanel(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._layout.addStretch()

        self._process_all_button = QPushButton("Process All")
        self._process_all_button.setEnabled(True)
        self._layout.addWidget(self._process_all_button)

        self._detect_2d_skeletons_button = QPushButton("Detect 2d Skeletons in Videos")
        self._detect_2d_skeletons_button.setEnabled(True)
        self._layout.addWidget(self._detect_2d_skeletons_button)

        self._triangulate_3d_data_button = QPushButton("Triangulate 3d Data")
        self._triangulate_3d_data_button.setEnabled(True)
        self._layout.addWidget(self._triangulate_3d_data_button)

        self._mediapipe_confidence_cutoff_form_layout = (
            self._make_mediapipe_confidence_cutoff_layout()
        )
        self._layout.addLayout(self._mediapipe_confidence_cutoff_form_layout)

        self._visualize_freemocap_session_button = QPushButton(
            "TO DO - Visualize Freemocap Session"
        )
        self._visualize_freemocap_session_button.setEnabled(False)
        self._layout.addWidget(self._visualize_freemocap_session_button)

        # self._visualize_freemocap_session_button.clicked.connect(
        #     self._visualize_freemocap_session
        # )

        self._open_in_blender_button = QPushButton(
            "Export to Blender (Freezes GUI, sorry!)"
        )
        self._open_in_blender_button.setEnabled(True)
        self._layout.addWidget(self._open_in_blender_button)

        self._layout.addStretch()

    @property
    def process_all_button(self):
        return self._process_all_button

    @property
    def detect_2d_skeletons_button(self):
        return self._detect_2d_skeletons_button

    @property
    def mediapipe_confidence_cutoff_threshold(self) -> float:
        return float(self._mediapipe_confidence_cutoff_line_edit_widget.text())

    @property
    def triangulate_3d_data_button(self):
        return self._triangulate_3d_data_button

    @property
    def open_in_blender_button(self):
        return self._open_in_blender_button

    def _make_mediapipe_confidence_cutoff_layout(self):
        layout = QFormLayout()
        self._mediapipe_confidence_cutoff_line_edit_widget = (
            self._create_mediapipe_confidence_cutoff_line_edit_widget()
        )
        layout.addRow(
            "Mediapipe 2d confidence cut-off:",
            self._mediapipe_confidence_cutoff_line_edit_widget,
        )

        return layout

    def _create_mediapipe_confidence_cutoff_line_edit_widget(self):
        q_line_edit_widget = QLineEdit()
        q_line_edit_widget.setText(str(default_mediapipe_confidence_threshold))

        q_line_edit_widget.setToolTip(mediapipe_confidence_cutoff_tool_tip_str)

        return q_line_edit_widget
