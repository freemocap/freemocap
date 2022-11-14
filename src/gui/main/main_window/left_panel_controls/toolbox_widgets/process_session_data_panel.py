import logging

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QCheckBox,
    QFormLayout,
    QLineEdit,
    QFileDialog,
    QLabel,
)

from src.blender_stuff.get_best_guess_of_blender_path import (
    get_best_guess_of_blender_path,
)
from src.core_processes.mediapipe_stuff.mediapipe_default_settings import (
    default_mediapipe_confidence_threshold,
)

from src.gui.main.tool_tips.tool_tips_strings import (
    mediapipe_confidence_cutoff_tool_tip_str,
)

logger = logging.getLogger(__name__)


class ProcessSessionDataPanel(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._layout.addStretch()

        self._process_all_button = QPushButton("Process All Steps Below")
        self._process_all_button.setEnabled(True)
        self._layout.addWidget(self._process_all_button)

        self._open_in_blender_automatically_checkbox = QCheckBox(
            "Open in Blender automatically"
        )
        self._open_in_blender_automatically_checkbox.setChecked(True)
        self._layout.addWidget(self._open_in_blender_automatically_checkbox)

        self._detect_2d_skeletons_button = QPushButton(
            "(a) - Detect 2d Skeletons in Videos"
        )
        self._detect_2d_skeletons_button.setEnabled(True)
        self._layout.addWidget(self._detect_2d_skeletons_button)

        self._triangulate_3d_data_button = QPushButton("(b) - Triangulate 3d Data")
        self._triangulate_3d_data_button.setEnabled(True)
        self._layout.addWidget(self._triangulate_3d_data_button)

        self._use_triangulate_ransac_checkbox = QCheckBox(
            "Use `anipose.triangulate_ransac() - EXPERIMENTAL"
        )
        self._use_triangulate_ransac_checkbox.setChecked(False)
        self._layout.addWidget(self._use_triangulate_ransac_checkbox)

        self._mediapipe_confidence_cutoff_form_layout = (
            self._make_mediapipe_confidence_cutoff_layout()
        )
        self._layout.addLayout(self._mediapipe_confidence_cutoff_form_layout)

        self._gap_fill_filter_origin_align_button = QPushButton(
            "(c) - Post-process data"
        )
        self._gap_fill_filter_origin_align_button.setToolTip(
            "Gap Fill, Butterworth Filter, and Origin Align Skeletons"
        )
        self._layout.addWidget(self._gap_fill_filter_origin_align_button)

        self._convert_npy_to_csv_button = QPushButton(
            "(d) - Convert 3D npy data to csv"
        )
        self._layout.addWidget(self._convert_npy_to_csv_button)

        self._layout.addStretch()

    @property
    def process_all_button(self):
        return self._process_all_button

    @property
    def open_in_blender_automatically_checkbox(self):
        return self._open_in_blender_automatically_checkbox

    @property
    def detect_2d_skeletons_button(self):
        return self._detect_2d_skeletons_button

    @property
    def mediapipe_confidence_cutoff_threshold(self) -> float:
        return float(self._mediapipe_confidence_cutoff_line_edit_widget.text())

    @property
    def use_triangulate_ransac_checkbox(self):
        return self._use_triangulate_ransac_checkbox

    @property
    def convert_npy_to_csv_button(self):
        return self._convert_npy_to_csv_button

    @property
    def triangulate_3d_data_button(self):
        return self._triangulate_3d_data_button

    @property
    def gap_fill_filter_origin_align_button(self):
        return self._gap_fill_filter_origin_align_button

    @property
    def blender_exe_path_str(self):
        return self._blender_exe_path_str

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
