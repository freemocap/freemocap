import logging
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QCheckBox,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QLabel,
    QFileDialog,
    QRadioButton,
)

from src.core_processes.capture_volume_calibration.charuco_board_detection.dataclasses.charuco_board_definition import (
    CharucoBoardDefinition,
)
from src.core_processes.capture_volume_calibration.charuco_board_detection.default_charuco_square_size import (
    default_charuco_square_size_mm,
)
from src.gui.main.style_stuff.styled_widgets.panel_section_title import (
    PanelSectionTitle,
)

logger = logging.getLogger(__name__)


class CalibrateCaptureVolumePanel(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._layout.addStretch()

        self._layout.addWidget(PanelSectionTitle("Calibration Data Source"))
        self._use_most_recent_calibration_radio_button = QRadioButton(
            "Use Most Recent Calibration"
        )
        self._use_most_recent_calibration_radio_button.toggled.connect(
            self._handle_use_previous_calibration_radio_button_toggled
        )
        self._layout.addWidget(self._use_most_recent_calibration_radio_button)

        self._load_camera_calibration_radio_button = QRadioButton(
            "Load Camera Calibration .toml file..."
        )
        self._layout.addWidget(self._load_camera_calibration_radio_button)
        self._load_camera_calibration_radio_button.toggled.connect(
            self._handle_load_camera_calibration_radio_button_toggled
        )

        self._load_calibration_toml_dialog_button = QPushButton(
            "Load Camera Calibration TOML..."
        )
        self._layout.addWidget(self._load_calibration_toml_dialog_button)
        self._load_calibration_toml_dialog_button.clicked.connect(
            self._open_load_camera_calibration_toml_dialog
        )
        self._load_calibration_toml_dialog_button.setToolTip(
            "locate the camera_calibration.toml file from a previous calibration"
        )

        self._user_selected_camera_calibration_toml_path_label = QLabel(
            "- No Camera Calibration TOML Loaded -"
        )
        self._user_selected_camera_calibration_toml_path_label.setWordWrap(True)
        self._layout.addWidget(self._user_selected_camera_calibration_toml_path_label)

        self._load_calibration_toml_dialog_button.setEnabled(False)
        self._user_selected_camera_calibration_toml_path_label.setEnabled(False)

        self._calibrate_from_synchronized_videos_radio_button = QRadioButton(
            "Calibrate from `synchronized_videos` folder"
        )
        self._layout.addWidget(self._calibrate_from_synchronized_videos_radio_button)
        self._calibrate_from_synchronized_videos_radio_button.toggled.connect(
            self._handle_calibrate_from_synchronized_videos_radio_button_toggled
        )

        self._record_calibration_videos_radio_button = QRadioButton(
            "Record New Calibration Videos"
        )
        self._layout.addWidget(self._record_calibration_videos_radio_button)
        self._record_calibration_videos_radio_button.setChecked(True)
        self._record_calibration_videos_radio_button.toggled.connect(
            self._handle_record_calibration_videos_radio_button_toggled
        )
        # start/stop recording button layout
        record_buttons_layout = QVBoxLayout()
        self._layout.addLayout(record_buttons_layout)

        self._start_recording_button = QPushButton("Begin Recording")
        record_buttons_layout.addWidget(self._start_recording_button)

        self._stop_recording_button = QPushButton("Stop Recording")
        self._stop_recording_button.setEnabled(False)
        record_buttons_layout.addWidget(self._stop_recording_button)
        self._process_automatically_checkbox = QCheckBox(
            "Process Calibration Videos Automatically"
        )
        self._process_automatically_checkbox.setChecked(True)
        self._process_automatically_checkbox.stateChanged.connect(
            self._enable_or_disable_calibrate_from_videos_button
        )
        self._layout.addWidget(self._process_automatically_checkbox)

        self._layout.addWidget(QLabel("___"), alignment=Qt.AlignCenter)

        camera_warning_qlabel = QLabel(
            "NOTE - For faster processing, shut down your cameras when you're done recording (i.e. press `Stop Cameras` in the 'Cameras' tab)"
        )
        camera_warning_qlabel.setWordWrap(True)
        self._layout.addWidget(camera_warning_qlabel)

        self._layout.addWidget(
            QLabel("Calibrate Capture Volume"), alignment=Qt.AlignCenter
        )

        self._calibrate_capture_volume_from_videos_button = QPushButton(
            "Calibrate Capture Volume From Videos"
        )
        self._calibrate_capture_volume_from_videos_button.setEnabled(True)
        self._calibrate_capture_volume_from_videos_button.setToolTip(
            "Looks for a `calibration_videos` folder first, reverting to `synchronized_videos` if not found"
        )
        self._layout.addWidget(
            self._calibrate_capture_volume_from_videos_button,
        )

        self._layout.addWidget(
            QLabel("Calibration Parameters:"), alignment=Qt.AlignCenter
        )

        qlabel_link_to_charuco_board = QLabel()
        qlabel_link_to_charuco_board.setText(
            '<a href="https://raw.githubusercontent.com/freemocap/freemocap/main/assets/charuco/charuco_board_image_highRes.png">Link to Charuco Board Image</a>'
        )
        qlabel_link_to_charuco_board.setOpenExternalLinks(True)
        qlabel_link_to_charuco_board.setWordWrap(True)
        self._layout.addWidget(qlabel_link_to_charuco_board)

        self._charuco_square_size_form_layout = QFormLayout()
        self._charuco_square_size_line_edit_widget = QLineEdit()
        self._charuco_square_size_line_edit_widget.setToolTip(
            "The length of one of the edges of the black squares in the calibration board in mm"
        )
        self._charuco_square_size_line_edit_widget.setText(
            str(default_charuco_square_size_mm)
        )
        self._charuco_square_size_form_layout.addRow(
            "Charuco Square Size (mm):", self._charuco_square_size_line_edit_widget
        )

        self._layout.addLayout(self._charuco_square_size_form_layout)

        self._layout.addWidget(QLabel("Charuco Checkerboard Type:"))
        self._charuco_board_definition = CharucoBoardDefinition()
        self._charuco_combo_box = QComboBox()
        self._charuco_combo_box.addItem("Pre-Alpha (5x7 squares)")
        # self._charuco_combo_box.addItem("Bigger Squares (3x5 squares)")

        self._layout.addWidget(self._charuco_combo_box)

        self._layout.addStretch()

    @property
    def process_recording_automatically_checkbox(self):
        return self._process_automatically_checkbox

    @property
    def start_recording_button(self):
        return self._start_recording_button

    @property
    def stop_recording_button(self):
        return self._stop_recording_button

    @property
    def calibrate_capture_volume_from_videos_button(self):
        return self._calibrate_capture_volume_from_videos_button

    @property
    def use_previous_calibration_box_is_checked(self):
        return self._use_most_recent_calibration_radio_button.isChecked()

    @property
    def load_camera_calibration_checkbox_is_checked(self):
        return self._load_camera_calibration_radio_button.isChecked()

    @property
    def charuco_square_size(self) -> float:
        return float(self._charuco_square_size_line_edit_widget.text())

    @property
    def charuco_combo_box_selection(self):
        return self._charuco_combo_box.currentText()

    @property
    def user_selected_calibration_toml_path(self):
        return self._user_selected_camera_calibration_toml_path_label.text()

    def _enable_or_disable_calibrate_from_videos_button(self):
        logger.debug("Process calibration videos automatically checkbox state changed")
        if self._process_automatically_checkbox.isChecked():
            self._calibrate_capture_volume_from_videos_button.setEnabled(False)
        else:
            self._calibrate_capture_volume_from_videos_button.setEnabled(True)

    def change_button_states_on_record_start(self):
        self._start_recording_button.setEnabled(False)
        self._start_recording_button.setText("Recording...")
        self._stop_recording_button.setEnabled(True)

    def change_button_states_on_record_stop(self):
        self._stop_recording_button.setEnabled(False)
        self._start_recording_button.setEnabled(True)
        self._start_recording_button.setText("Begin Recording")
        self._calibrate_capture_volume_from_videos_button.setEnabled(True)

    def _handle_use_previous_calibration_radio_button_toggled(self):

        self._disable_load_camera_calibration_stuff()
        self._disable_record_new_calibration_videos_stuff()
        self._enable_calibration_parameters_stuff(False)

    def _handle_load_camera_calibration_radio_button_toggled(self):
        self._load_calibration_toml_dialog_button.setEnabled(True)
        self._user_selected_camera_calibration_toml_path_label.setEnabled(True)
        self._disable_record_new_calibration_videos_stuff()
        self._enable_calibration_parameters_stuff(False)

    def _handle_calibrate_from_synchronized_videos_radio_button_toggled(self):
        self._disable_record_new_calibration_videos_stuff()
        self._disable_load_camera_calibration_stuff()
        self._enable_calibration_parameters_stuff(True)
        self._calibrate_capture_volume_from_videos_button.setEnabled(True)

    def _handle_record_calibration_videos_radio_button_toggled(self):
        self._enable_record_new_calibration_videos_stuff()
        self._disable_load_camera_calibration_stuff()
        self._enable_calibration_parameters_stuff(True)

    def _open_load_camera_calibration_toml_dialog(self):
        # from this tutorial - https://www.youtube.com/watch?v=gg5TepTc2Jg&t=649s
        calibration_toml_path_selection = QFileDialog.getOpenFileName(
            self,
            "Select 'toml' containing camera calibration info (Note - this is the 'toml' file produced by the `anipose` calibration process)",
            str(Path.home()),
            "Camera Calibration TOML (*.toml)",
        )
        self.calibration_toml_path_str = calibration_toml_path_selection[0]
        logger.info(
            f"User selected camera calibration toml path:{self.calibration_toml_path_str}"
        )
        self._user_selected_camera_calibration_toml_path_label.setText(
            self.calibration_toml_path_str
        )

    def _disable_record_new_calibration_videos_stuff(self):
        self._start_recording_button.setEnabled(False)
        self._stop_recording_button.setEnabled(False)
        self._process_automatically_checkbox.setEnabled(False)
        self._calibrate_capture_volume_from_videos_button.setEnabled(False)

    def _enable_record_new_calibration_videos_stuff(self):
        self._start_recording_button.setEnabled(True)
        self._stop_recording_button.setEnabled(True)
        self._process_automatically_checkbox.setEnabled(True)
        self._calibrate_capture_volume_from_videos_button.setEnabled(True)

    def _disable_load_camera_calibration_stuff(self):
        self._load_calibration_toml_dialog_button.setEnabled(False)
        self._user_selected_camera_calibration_toml_path_label.setEnabled(False)

    def _enable_calibration_parameters_stuff(self, bool_in: bool):
        self._charuco_combo_box.setEnabled(bool_in)
        self._charuco_square_size_line_edit_widget.setEnabled(bool_in)
