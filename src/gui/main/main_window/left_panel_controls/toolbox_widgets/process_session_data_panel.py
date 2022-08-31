import numpy as np
from PyQt6 import QtCore
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QCheckBox

from src.export_stuff.blender_stuff.export_to_blender import (
    export_to_blender,
)
from src.gui.main.app_state.app_state import APP_STATE


class ProcessSessionDataPanel(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._layout.addStretch()
        processing_buttons_layout = QVBoxLayout()
        self._layout.addLayout(processing_buttons_layout)

        self._process_all_button = QPushButton("Process All")
        self._process_all_button.setEnabled(True)
        processing_buttons_layout.addWidget(self._process_all_button)

        self._detect_2d_skeletons_button = QPushButton("Detect 2d Skeletons in Videos")
        self._detect_2d_skeletons_button.setEnabled(True)
        processing_buttons_layout.addWidget(self._detect_2d_skeletons_button)

        self._triangulate_3d_data_button = QPushButton("Triangulate 3d Data")
        self._triangulate_3d_data_button.setEnabled(True)
        processing_buttons_layout.addWidget(self._triangulate_3d_data_button)

        # self._visualize_freemocap_session_button = QPushButton(
        #     "Visualize Freemocap Session"
        # )
        # self._visualize_freemocap_session_button.setEnabled(True)
        # self._visualize_freemocap_session_button.clicked.connect(
        #     self._visualize_freemocap_session
        # )

        self._open_in_blender_button = QPushButton(
            "Open Session in Blender (Freezes GUI, sorry!)"
        )
        self._open_in_blender_button.setEnabled(True)
        processing_buttons_layout.addWidget(self._open_in_blender_button)
        # processing_buttons_layout.addWidget(self._visualize_freemocap_session_button)
        self._layout.addStretch()

    @property
    def process_all_button(self):
        return self._process_all_button

    @property
    def detect_2d_skeletons_button(self):
        return self._detect_2d_skeletons_button

    @property
    def triangulate_3d_data_button(self):
        return self._triangulate_3d_data_button

    @property
    def open_in_blender_button(self):
        return self._open_in_blender_button
