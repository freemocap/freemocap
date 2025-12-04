import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QFormLayout,
    QLabel,
    QRadioButton,
    QCheckBox,
    QComboBox,
    QFrame,
)
from skellycam import SkellyCamControllerWidget, SkellyCamWidget

from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import CHARUCO_BOARDS
from freemocap.gui.qt.utilities.save_and_load_gui_state import GuiState, load_gui_state, save_gui_state
from freemocap.gui.qt.widgets.calibration_guide_link_qlabel import CalibrationGuideLinkQLabel
from freemocap.system.paths_and_filenames.file_and_folder_names import SPARKLES_EMOJI_STRING, SKULL_EMOJI_STRING
from freemocap.system.paths_and_filenames.path_getters import (
    create_new_recording_folder_path,
    create_new_default_recording_name,
    get_gui_state_json_path,
)

CALIBRATION_RECORDING_BUTTON_TEXT = "\U0001f534 \U0001f4d0 Start Calibration Recording"
MOCAP_RECORDING_BUTTON_TEXT = f"{SKULL_EMOJI_STRING} {SPARKLES_EMOJI_STRING} Start Motion Capture Recording"
CALIBRATION_DOCS_LINK = "https://freemocap.github.io/documentation/multi-camera-calibration.html"
logger = logging.getLogger(__name__)


class CameraControllerGroupBox(QGroupBox):
    controller_group_box_calibration_updated = Signal()

    def __init__(self, skellycam_widget: SkellyCamWidget, gui_state: GuiState, parent=None):
        super().__init__(parent=parent)
        self.setStyleSheet("font-size: 12px;")
        self._skellycam_widget = skellycam_widget
        self._skellycam_controller = SkellyCamControllerWidget(
            camera_viewer_widget=skellycam_widget,
            parent=self,
        )
        self._skellycam_controller.check_recording_type = (self.check_recording_type,)

        self.gui_state = gui_state

        self._layout = QHBoxLayout()
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.setLayout(self._layout)

        create_calibration_recording_option_layout = self._create_calibration_recording_option_layout()

        vbox = QVBoxLayout()
        vbox.addLayout(self._make_options_layout())
        vbox.addLayout(self._create_mocap_recording_option_layout())
        vbox.addLayout(create_calibration_recording_option_layout)

        self._layout.addLayout(vbox)

        self._calibration_videos_radio_button.toggled.connect(self._set_record_button_text)
        self._annotate_charuco_checkbox.toggled.connect(self._on_annotate_charuco_checkbox_changed)
        self._mocap_videos_radio_button.toggled.connect(self._set_record_button_text)
        self._skellycam_widget.cameras_connected_signal.connect(lambda: self._start_recording_button.setEnabled(True))
        self._stop_recording_button.clicked.connect(self._set_record_button_text)

        self._auto_process_videos_checkbox.toggled.connect(self._on_auto_process_videos_checkbox_changed)
        self._generate_jupyter_notebook_checkbox.toggled.connect(self._on_generate_jupyter_notebook_checkbox_changed)
        self._auto_open_in_blender_checkbox.toggled.connect(self._on_auto_open_in_blender_checkbox_changed)
        self._charuco_square_size_line_edit.textEdited.connect(self._on_charuco_square_size_line_edit_changed)
        self._use_charuco_as_groundplane_checkbox.toggled.connect(self._on_use_charuco_groundplane_checkbox_changed)
        self._board_dropdown.currentTextChanged.connect(self._on_charuco_board_dropdown_changed)

    @property
    def mocap_videos_radio_button_checked(self) -> bool:
        return self._mocap_videos_radio_button.isChecked()

    @property
    def calibration_videos_radio_button_checked(self) -> bool:
        return self._calibration_videos_radio_button.isChecked()

    @property
    def auto_process_videos_checked(self) -> bool:
        return self._auto_process_videos_checkbox.isChecked()

    @property
    def auto_open_in_blender_checked(self) -> bool:
        return self._auto_open_in_blender_checkbox.isChecked()

    @property
    def generate_jupyter_notebook_checked(self) -> bool:
        return self._generate_jupyter_notebook_checkbox.isChecked()

    @property
    def charuco_square_size(self) -> float:
        return float(self._charuco_square_size_line_edit.text())

    @property
    def use_charuco_as_groundplane(self) -> bool:
        return self._use_charuco_as_groundplane_checkbox.isChecked()

    @property
    def charuco_board_name(self) -> str:
        return self._board_dropdown.currentText()

    def check_recording_type(self) -> str:
        if self._mocap_videos_radio_button.isChecked():
            return "mocap"
        elif self._calibration_videos_radio_button.isChecked():
            return "calibration"
        else:
            raise ValueError("No recording type selected")

    def _create_mocap_recording_option_layout(self) -> QHBoxLayout:
        hbox = QHBoxLayout()
        hbox.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._mocap_videos_radio_button = QRadioButton("Record Motion Capture Videos")

        hbox.addWidget(self._mocap_videos_radio_button)

        self._mocap_videos_radio_button.setChecked(True)
        hbox.addWidget(QLabel(" - "))
        self._auto_process_videos_checkbox = QCheckBox("Auto Process Videos")
        self._auto_process_videos_checkbox.setChecked(self.gui_state.auto_process_videos_on_save)
        hbox.addWidget(self._auto_process_videos_checkbox)

        self._generate_jupyter_notebook_checkbox = QCheckBox("Generate Jupyter Notebook")
        self._generate_jupyter_notebook_checkbox.setChecked(self.gui_state.generate_jupyter_notebook)
        hbox.addWidget(self._generate_jupyter_notebook_checkbox)

        self._auto_open_in_blender_checkbox = QCheckBox("Auto Open in Blender")
        self._auto_open_in_blender_checkbox.setChecked(self.gui_state.auto_open_in_blender)
        hbox.addWidget(self._auto_open_in_blender_checkbox)
        return hbox

    def _create_calibration_recording_option_layout(self) -> QVBoxLayout:
        vbox = QVBoxLayout()

        # -------- First Row (Calibration Radio, Board Dropdown, Square Size) --------
        hbox_top = QHBoxLayout()
        hbox_top.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._calibration_videos_radio_button = QRadioButton("Record Calibration Videos")
        hbox_top.addWidget(self._calibration_videos_radio_button)
        hbox_top.addWidget(QLabel(" - "))

        hbox_top.addWidget(QLabel("Charuco square size (mm)", parent=self))
        self._charuco_square_size_line_edit = QLineEdit(parent=self)
        self._charuco_square_size_line_edit.setFixedWidth(60)
        self._charuco_square_size_line_edit.setText(str(self.gui_state.charuco_square_size))
        self._charuco_square_size_line_edit.setToolTip(
            "The length of one of the edges of the black squares in the calibration board in mm"
        )
        hbox_top.addWidget(self._charuco_square_size_line_edit)

        hbox_top.addWidget(QLabel("Charuco Board:"))
        self._board_dropdown = self._create_board_dropdown()
        self._board_dropdown.setCurrentText(self.gui_state.charuco_board_name)
        hbox_top.addWidget(self._board_dropdown)

        hbox_top.addStretch()

        hbox_bottom = QHBoxLayout()
        hbox_bottom.setAlignment(Qt.AlignmentFlag.AlignLeft)
        # Add indentation spacing (adjust the width as needed)
        indent_spacer = QLabel("")
        indent_spacer.setFixedWidth(80)  # Adjust this value for more/less indentation
        hbox_bottom.addWidget(indent_spacer)
        self._annotate_charuco_checkbox = QCheckBox("Charuco Overlay (requires camera restart)")
        self._annotate_charuco_checkbox.setChecked(self.gui_state.annotate_charuco_images)
        self._skellycam_widget.annotate_images = self._annotate_charuco_checkbox.isChecked()
        hbox_bottom.addWidget(self._annotate_charuco_checkbox)

        self._use_charuco_as_groundplane_checkbox = QCheckBox("Use initial board position as origin")
        self._use_charuco_as_groundplane_checkbox.setChecked(self.gui_state.use_charuco_as_groundplane)
        hbox_bottom.addWidget(self._use_charuco_as_groundplane_checkbox)

        hbox_bottom.addWidget(CalibrationGuideLinkQLabel(parent=self))
        # hbox_bottom.addStretch()

        vbox.addLayout(hbox_top)
        vbox.addLayout(hbox_bottom)

        return vbox

    def _open_calibration_docs(self, url: str) -> None:
        """Open the calibration documentation in the default web browser."""
        QDesktopServices.openUrl(url)

    def _make_options_layout(self) -> QHBoxLayout:
        options_vbox = QHBoxLayout()

        options_vbox.addLayout(self._make_record_button_layout())

        options_vbox.addLayout(self._create_videos_will_save_to_layout())

        return options_vbox

    def _create_horizontal_separator(self) -> QFrame:
        """Create a horizontal line separator widget."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setLineWidth(1)
        # Optional: Add some styling to make it more visible or subtle
        separator.setStyleSheet(
            """
            QFrame {
                color: #d0d0d0;
                margin-top: 5px;
                margin-bottom: 5px;
            }
        """
        )
        return separator

    def _make_record_button_layout(self) -> QVBoxLayout:
        button_vbox = QVBoxLayout()
        self._start_recording_button = self._skellycam_controller.start_recording_button
        self._stop_recording_button = self._skellycam_controller.stop_recording_button
        self._start_recording_button.setStyleSheet("font-size: 14px;")
        self._stop_recording_button.setStyleSheet("font-size: 14px;")
        self._start_recording_button.setText(MOCAP_RECORDING_BUTTON_TEXT)
        self._start_recording_button.setObjectName("start_recording_button")
        self._stop_recording_button.setObjectName("stop_recording_button")
        self._start_recording_button.show()
        self._start_recording_button.setEnabled(False)
        self._stop_recording_button.show()
        button_vbox.addWidget(self._start_recording_button)
        button_vbox.addWidget(self._stop_recording_button)
        return button_vbox

    def _create_videos_will_save_to_layout(self) -> QVBoxLayout:
        vbox = QVBoxLayout()

        session_path_hbox = QHBoxLayout()
        session_path_hbox.setAlignment(Qt.AlignmentFlag.AlignLeft)
        vbox.addLayout(session_path_hbox)
        recording_path_full = self.get_new_recording_path()
        recording_name = Path(recording_path_full).stem

        recording_name_hbox = QHBoxLayout()
        vbox.addLayout(recording_name_hbox)
        recording_name_key_label = QLabel("Recording Name: ")
        recording_name_hbox.addWidget(recording_name_key_label)
        self._recording_name_label = QLabel(f"{recording_name}")
        self._recording_name_label.setStyleSheet("font-family: monospace;")
        recording_name_hbox.addWidget(self._recording_name_label)

        recording_string_tag_form_layout = QFormLayout(parent=self)
        self._recording_string_tag_line_edit = QLineEdit(parent=self)
        self._recording_string_tag_line_edit.setPlaceholderText("(Optional)")
        self._recording_string_tag_line_edit.setMaxLength(200)
        self._recording_string_tag_line_edit.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        recording_string_tag_form_layout.addRow("Tag:", self._recording_string_tag_line_edit)
        recording_name_hbox.addWidget(QLabel(" - "))
        recording_name_hbox.addLayout(recording_string_tag_form_layout)

        full_path_hbox = QHBoxLayout()
        full_path_hbox.setAlignment(Qt.AlignmentFlag.AlignLeft)
        vbox.addLayout(full_path_hbox)
        full_path_key_label = QLabel("Full Path: ")
        full_path_hbox.addWidget(full_path_key_label)
        self._full_path_label = QLabel(recording_path_full)
        self._full_path_label.setWordWrap(True)
        self._full_path_label.setStyleSheet("font-family: monospace;")
        full_path_hbox.addWidget(self._full_path_label)

        return vbox

    def _create_board_dropdown(self) -> QComboBox:
        board_dropdown = QComboBox()
        board_dropdown.setToolTip("Select the Charuco board to use for calibration")
        board_dropdown.setFixedWidth(150)
        board_dropdown.setStyleSheet("QComboBox { font-size: 12px; }")
        board_dropdown.setEnabled(True)
        board_dropdown.setEditable(False)
        board_dropdown.addItems(list(CHARUCO_BOARDS.keys()))
        return board_dropdown

    def get_new_recording_path(self) -> str:
        return create_new_recording_folder_path(recording_name=self._get_recording_name())

    def update_recording_name_string(self) -> None:
        self._recording_name_label.setText(Path(self.get_new_recording_path()).stem)
        self._full_path_label.setText(f"{self.get_new_recording_path()}")

    def _get_recording_name_string_tag(self) -> str:
        try:
            tag = self._recording_string_tag_line_edit.text()
            tag = tag.replace("   ", " ")
            tag = tag.replace("  ", " ")
            tag = tag.replace(" ", "_")
            return tag
        except Exception:
            return ""

    def _get_recording_name(self) -> str:
        name = create_new_default_recording_name()
        if self._calibration_videos_radio_button.isChecked():
            name = f"{name}_calibration"

        tag = self._get_recording_name_string_tag()
        if tag == "":
            return name
        else:
            return f"{name}__{self._get_recording_name_string_tag()}"

    def _set_record_button_text(self) -> None:
        if self._calibration_videos_radio_button.isChecked():
            self.setProperty("calibration_videos_radio_button_checked", True)
            self._start_recording_button.setText(CALIBRATION_RECORDING_BUTTON_TEXT)
        else:
            self.setProperty("calibration_videos_radio_button_checked", False)
            self._start_recording_button.setText(MOCAP_RECORDING_BUTTON_TEXT)
        self.style().polish(self)

    def _on_annotate_charuco_checkbox_changed(self) -> None:
        self._skellycam_widget.annotate_images = self._annotate_charuco_checkbox.isChecked()
        self.gui_state.annotate_charuco_images = self._annotate_charuco_checkbox.isChecked()
        save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())

    def _on_use_charuco_groundplane_checkbox_changed(self) -> None:
        self.gui_state.use_charuco_as_groundplane = self._use_charuco_as_groundplane_checkbox.isChecked()
        save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())
        self.controller_group_box_calibration_updated.emit()

    def _on_auto_process_videos_checkbox_changed(self) -> None:
        self.gui_state.auto_process_videos_on_save = self._auto_process_videos_checkbox.isChecked()
        save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())

    def _on_generate_jupyter_notebook_checkbox_changed(self) -> None:
        self.gui_state.generate_jupyter_notebook = self._generate_jupyter_notebook_checkbox.isChecked()
        save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())

    def _on_auto_open_in_blender_checkbox_changed(self) -> None:
        self.gui_state.auto_open_in_blender = self._auto_open_in_blender_checkbox.isChecked()
        save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())

    def _on_charuco_square_size_line_edit_changed(self) -> None:
        try:
            self.gui_state.charuco_square_size = float(self._charuco_square_size_line_edit.text())
        except ValueError:
            return
        save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())
        self.controller_group_box_calibration_updated.emit()

    def _on_charuco_board_dropdown_changed(self) -> None:
        selected_board_name = self._board_dropdown.currentText()
        self.gui_state.charuco_board_name = selected_board_name
        save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())
        self.controller_group_box_calibration_updated.emit()

    @Slot()
    def charuco_option_updated(self) -> None:
        self.gui_state = load_gui_state(file_pathstring=get_gui_state_json_path())
        self._board_dropdown.setCurrentText(self.gui_state.charuco_board_name)
        self._charuco_square_size_line_edit.setText(str(self.gui_state.charuco_square_size))
        self._use_charuco_as_groundplane_checkbox.setChecked(self.gui_state.use_charuco_as_groundplane)
