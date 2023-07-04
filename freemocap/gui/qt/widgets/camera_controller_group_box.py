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
)
from skellycam import SkellyCamRecordButtons

from freemocap.core_processes.capture_volume_calibration.charuco_stuff.default_charuco_square_size import (
    default_charuco_square_size_mm,
)
from freemocap.system.paths_and_filenames.path_getters import create_new_recording_folder_path, \
    create_new_default_recording_name


class RecordingNameGenerator:
    pass


class CameraControllerGroupBox(QGroupBox):
    def __init__(self, skellycam_controller: SkellyCamRecordButtons, parent=None):
        super().__init__(parent=parent)
        self._skellycam_controller = skellycam_controller
        skellycam_controller.start_recording_button.setObjectName("start_recording_button")
        skellycam_controller.stop_recording_button.setObjectName("stop_recording_button")

        # self.setFlat(True)
        self._layout = QHBoxLayout()
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setLayout(self._layout)

        self._layout.addWidget(self._skellycam_controller)

        motion_capture_recording_options_layout = self._create_mocap_recording_option_layout()
        self._layout.addLayout(motion_capture_recording_options_layout)

        calibration_recording_option_layout = self._create_calibration_recording_option_layout()
        self._layout.addLayout(calibration_recording_option_layout)

        self._layout.addLayout(self._create_videos_will_save_to_layout())



    def _create_videos_will_save_to_layout(self):
        vbox = QVBoxLayout()

        hbox = QHBoxLayout()
        hbox.setAlignment(Qt.AlignmentFlag.AlignLeft)
        vbox.addLayout(hbox)

        videos_will_save_to_label = QLabel("Recording Path: ")
        videos_will_save_to_label.setStyleSheet("font-size: 12px;")
        hbox.addWidget(videos_will_save_to_label)
        self._recording_path_label = QLabel(f"{self.get_new_recording_path()}")
        self._recording_path_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        hbox.addWidget(self._recording_path_label)

        recording_string_tag_form_layout = QFormLayout(parent=self)
        self._recording_string_tag_line_edit = QLineEdit(parent=self)
        self._recording_string_tag_line_edit.setPlaceholderText("(Optional)")
        recording_string_tag_form_layout.addRow("Tag:", self._recording_string_tag_line_edit)
        hbox.addLayout(recording_string_tag_form_layout)



        lag_note_label = QLabel("NOTE: If you experience lag in your camera views, decrease the resolution and/or use fewer cameras. We are working on a fix which should be done 'soon' (written: 2023-04-05)")
        lag_note_label.setStyleSheet("font-size: 12px;")
        lag_note_label.setWordWrap(True)
        vbox.addWidget(lag_note_label)

        return vbox

    def _create_mocap_recording_option_layout(self):
        hbox = QHBoxLayout()
        hbox.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._mocap_videos_radio_button = QRadioButton("Record Motion Capture Videos")
        hbox.addWidget(self._mocap_videos_radio_button)

        self._mocap_videos_radio_button.setChecked(True)
        hbox.addWidget(QLabel(" - "))
        self._auto_process_videos_checkbox = QCheckBox("Auto Process Videos on Save")
        self._auto_process_videos_checkbox.setChecked(True)
        hbox.addWidget(self._auto_process_videos_checkbox)

        self._generate_jupyter_notebook_checkbox = QCheckBox('Generate Jupyter Notebook')
        self._generate_jupyter_notebook_checkbox.setChecked(True)
        hbox.addWidget(self._generate_jupyter_notebook_checkbox)

        self._auto_open_in_blender_checkbox = QCheckBox("Auto Open in Blender")
        self._auto_open_in_blender_checkbox.setChecked(True)
        hbox.addWidget(self._auto_open_in_blender_checkbox)
        return hbox

    def _create_calibration_recording_option_layout(self):
        hbox = QHBoxLayout()
        hbox.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._calibration_videos_radio_button = QRadioButton("Record Calibration Videos")
        hbox.addWidget(self._calibration_videos_radio_button)
        hbox.addWidget(QLabel(" - "))
        self._calibration_videos_radio_button.toggled.connect(self._handle_calibration_videos_radio_button_changed)

        hbox.addWidget(QLabel("Charuco square size (mm)", parent=self))
        self._charuco_square_size_line_edit = QLineEdit(parent=self)
        self._charuco_square_size_line_edit.setFixedWidth(100)
        self._charuco_square_size_line_edit.setText(str(default_charuco_square_size_mm))
        self._charuco_square_size_line_edit.setToolTip(
            "The length of one of the edges of the black squares in the calibration board in mm"
        )
        hbox.addWidget(self._charuco_square_size_line_edit)
        hbox.addStretch()
        return hbox

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
        name = create_new_default_recording_name()
        if self._calibration_videos_radio_button.isChecked():
            name = f"{name}_calibration"

        tag = self._get_recording_name_string_tag()
        if tag == "":
            return name
        else:
            return f"{name}__{self._get_recording_name_string_tag()}"

    def _handle_calibration_videos_radio_button_changed(self, state):
        if self._calibration_videos_radio_button.isChecked():
            self.setProperty("calibration_videos_radio_button_checked", True)
            self._skellycam_controller.set_calibration_recordings_button_label(True)
        else:
            self.setProperty("calibration_videos_radio_button_checked", False)
            self._skellycam_controller.set_calibration_recordings_button_label(False)
        self.style().polish(self)
