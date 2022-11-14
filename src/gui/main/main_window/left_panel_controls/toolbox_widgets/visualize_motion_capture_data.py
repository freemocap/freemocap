import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QHBoxLayout,
)

from src.blender_stuff.get_best_guess_of_blender_path import (
    get_best_guess_of_blender_path,
)
from src.gui.main.style_stuff.styled_widgets.panel_section_title import (
    PanelSectionTitle,
)


logger = logging.getLogger(__name__)


class VisualizeMotionCaptureDataPanel(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._load_session_data_button = QPushButton(
            "Show Session Data Viewer",
        )
        self._load_session_data_button.setEnabled(True)
        self._layout.addWidget(self._load_session_data_button)
        self._load_session_data_button.clicked.connect(
            self._handle_load_session_data_button_clicked,
        )

        self._play_pause_button_layout = QHBoxLayout()
        self._layout.addLayout(self._play_pause_button_layout)

        self._play_button = QPushButton("TODO - Play")
        self._play_button.setEnabled(False)
        self._play_pause_button_layout.addWidget(self._play_button)
        self._play_button.clicked.connect(self._handle_play_button_clicked)

        self._pause_button = QPushButton("TODO - Pause")
        self._pause_button.setEnabled(False)
        self._play_pause_button_layout.addWidget(self._pause_button)
        self._pause_button.clicked.connect(self._handle_pause_button_clicked)

        self._layout.addWidget(QLabel("___"), alignment=Qt.AlignCenter)

        self._layout.addWidget(
            PanelSectionTitle("Export to Blender"), alignment=Qt.AlignCenter
        )

        self._blender_path_form_layout = self._make_blender_path_layout()
        self._layout.addLayout(self._blender_path_form_layout)

        self._generate_blend_file_button = QPushButton(
            "Generate `.blend` file (Freezes GUI, sorry!)"
        )
        self._generate_blend_file_button.setEnabled(True)
        self._layout.addWidget(self._generate_blend_file_button)

        self._should_pause_playback_bool = False

        self._should_pause_playback_bool = False

    @property
    def load_session_data_button(self):
        return self._load_session_data_button

    @property
    def generate_blend_file_button(self):
        return self._generate_blend_file_button

    @property
    def play_button(self):
        return self._play_button

    @property
    def pause_button(self):
        return self._pause_button

    @property
    def should_pause_playback_bool(self):
        return self._should_pause_playback_bool

    @property
    def blender_exe_path_str(self):
        return self._blender_exe_path_str

    def _handle_load_session_data_button_clicked(self):
        self._load_session_data_button.setEnabled(False)
        self._play_button.setEnabled(False)
        self._pause_button.setEnabled(True)

    def _handle_play_button_clicked(self):
        self._should_pause_playback_bool = False
        self._play_button.setEnabled(False)
        self._pause_button.setEnabled(True)

    def _handle_pause_button_clicked(self):
        self._should_pause_playback_bool = True
        self._play_button.setEnabled(True)
        self._pause_button.setEnabled(False)

    def _make_blender_path_layout(self):
        blender_path_layout = QVBoxLayout()

        self._open_blender_path_file_dialog_button = QPushButton(
            "Locate Blender Executable"
        )
        blender_path_layout.addWidget(self._open_blender_path_file_dialog_button)
        self._open_blender_path_file_dialog_button.clicked.connect(
            self._open_blender_path_file_dialog
        )
        self._open_blender_path_file_dialog_button.setToolTip(
            "This is the path executable that we will send the `blender export` subprocess command"
        )

        self._blender_exe_path_str = get_best_guess_of_blender_path()
        if self._blender_exe_path_str is None:
            self._blender_exe_path_str = " - Blender executable not specified - "
        self._current_blender_path_label = QLabel(self._blender_exe_path_str)
        # if self._blender_exe_path is None:
        #     self._open_blender_path_file_dialog()
        blender_path_layout.addWidget(self._current_blender_path_label)

        return blender_path_layout

    def _open_blender_path_file_dialog(self):
        # from this tutorial - https://www.youtube.com/watch?v=gg5TepTc2Jg&t=649s
        self._blender_exe_path_str = QFileDialog.getOpenFileName()
        self._blender_exe_path_str = self._blender_exe_path_str[0]
        logger.info(f"User selected Blender path:{self._blender_exe_path_str}")
        self._current_blender_path_label.setText(self._blender_exe_path_str)

