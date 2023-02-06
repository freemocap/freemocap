from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QFormLayout,
    QLabel,
    QRadioButton,
    QCheckBox,
    QWidget,
)
from skellycam import SkellyCamControllerWidget

from freemocap.core_processes.capture_volume_calibration.charuco_stuff.default_charuco_square_size import (
    default_charuco_square_size_mm,
)
from freemocap.system.paths_and_files_names import create_new_default_recording_name, create_new_recording_folder_path


class RecordingNameGenerator:
    pass


class CameraControllerGroupBox(QGroupBox):
    def __init__(self, skellycam_controller: SkellyCamControllerWidget, parent=None):
        super().__init__(parent=parent)
        self._skellycam_controller = skellycam_controller

        # self.setFlat(True)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        # self._layout.setContentsMargins(0, 0, 0, 0)
        # self._layout.setSpacing(0)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._layout.addWidget(self._skellycam_controller)

        self._recording_name_controller_row_layout = QHBoxLayout()
        self._layout.addLayout(self._recording_name_controller_row_layout)

        self._recording_string_tag_line_edit = QLineEdit(parent=self)
        self._recording_string_tag_line_edit.setPlaceholderText("(Optional)")
        # self._recording_string_tag_line_edit.setFixedWidth(300)
        recording_string_tag_form_layout = QFormLayout(parent=self)
        recording_string_tag_form_layout.addRow("Recording Name Tag", self._recording_string_tag_line_edit)
        self._recording_name_controller_row_layout.addLayout(recording_string_tag_form_layout)

        hbox = QHBoxLayout()
        hbox.setAlignment(Qt.AlignmentFlag.AlignLeft)
        hbox.addWidget(QLabel("Videos will save to folder: "))
        self._recording_path_label = QLabel(f"{self.get_new_recording_path()}")
        self._recording_path_label.setStyleSheet("font-family: monospace;")
        hbox.addWidget(self._recording_path_label)
        # self._recording_path_label.setStyleSheet("font-family: monospace; font-size: 12px; font-weight: bold;")
        self._layout.addLayout(hbox)

        recording_type_radio_button_layout = QVBoxLayout()
        self._layout.addLayout(recording_type_radio_button_layout)

        motion_capture_recording_options_layout = QHBoxLayout()
        motion_capture_recording_options_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._mocap_videos_radio_button = QRadioButton("Record Motion Capture Videos")
        motion_capture_recording_options_layout.addWidget(self._mocap_videos_radio_button)
        self._mocap_videos_radio_button.setChecked(True)

        motion_capture_recording_options_layout.addWidget(QLabel(" - "))

        self._auto_process_videos_checkbox = QCheckBox("Auto Process Videos on Save")
        self._auto_process_videos_checkbox.setChecked(True)
        motion_capture_recording_options_layout.addWidget(self._auto_process_videos_checkbox)

        self._auto_open_in_blender_checkbox = QCheckBox("Auto Open in Blender")
        self._auto_open_in_blender_checkbox.setChecked(True)
        motion_capture_recording_options_layout.addWidget(self._auto_open_in_blender_checkbox)
        self._layout.addLayout(motion_capture_recording_options_layout)

        calibration_recordings_options_layout = QHBoxLayout()

        calibration_recordings_options_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        calibration_recordings_options_layout.setSizeConstraint(
            motion_capture_recording_options_layout.sizeConstraint()
        )
        self._calibration_videos_radio_button = QRadioButton("Record Calibration Videos")
        calibration_recordings_options_layout.addWidget(self._calibration_videos_radio_button)
        calibration_recordings_options_layout.addWidget(QLabel(" - "))
        self._calibration_videos_radio_button.toggled.connect(self._handle_calibration_videos_radio_button_changed)

        charuco_square_size_form_layout = QFormLayout(parent=self)
        calibration_recordings_options_layout.addLayout(charuco_square_size_form_layout)
        self._charuco_square_size_line_edit = QLineEdit(parent=self)
        self._charuco_square_size_line_edit.setFixedWidth(100)
        self._charuco_square_size_label = QLabel("Charuco square size (mm)")
        self._charuco_square_size_line_edit.setText(str(default_charuco_square_size_mm))
        self._charuco_square_size_line_edit.setToolTip(
            "The length of one of the edges of the black squares in the calibration board in mm"
        )
        charuco_square_size_form_layout.addRow(self._charuco_square_size_label, self._charuco_square_size_line_edit)

        self._layout.addLayout(calibration_recordings_options_layout)

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
    def charuco_square_size(self) -> float:
        return float(self._charuco_square_size_line_edit.text())

    def get_new_recording_path(self):
        return create_new_recording_folder_path(recording_name=self._get_recording_name())

    def update_recording_name_string(self):
        self._recording_path_label.setText(self.get_new_recording_path())

    def _get_recording_name_string_tag(self):
        try:
            tag = self._recording_string_tag_line_edit.text()
            tag = tag.replace("   ", " ")
            tag = tag.replace("  ", " ")
            tag = tag.replace(" ", "_")
            return tag
        except:
            return ""

    def _get_recording_name(self):
        tag = self._get_recording_name_string_tag()
        if tag == "":
            return create_new_default_recording_name()
        else:
            return f"{create_new_default_recording_name()}__{self._get_recording_name_string_tag()}"

    def _handle_calibration_videos_radio_button_changed(self, state):
        if self._calibration_videos_radio_button.isChecked():
            self.setProperty("calibration_videos_radio_button_checked", True)
            self._skellycam_controller.set_calibration_recordings_button_label(True)
        else:
            self.setProperty("calibration_videos_radio_button_checked", False)
            self._skellycam_controller.set_calibration_recordings_button_label(False)
        self.style().polish(self)
