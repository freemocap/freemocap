import logging
import os
import threading
from pathlib import Path
from typing import Callable, Optional, Union

from PySide6.QtCore import Qt, Slot, Signal, QObject
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QLayout,
    QCheckBox,
    QComboBox,
)

from freemocap.data_layer.recording_models.recording_info_model import RecordingInfoModel
from freemocap.gui.qt.utilities.save_and_load_gui_state import GuiState, load_gui_state, save_gui_state
from freemocap.gui.qt.workers.anipose_calibration_thread_worker import (
    AniposeCalibrationThreadWorker,
)
from freemocap.system.paths_and_filenames.path_getters import (
    get_gui_state_json_path,
    get_last_successful_calibration_toml_path,
)

from freemocap.gui.qt.widgets.groundplane_failure_dialog import GroundPlaneCalibrationFailedDialog
from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import CHARUCO_BOARDS

logger = logging.getLogger(__name__)


class CalibrationControlPanel(QWidget):
    control_panel_calibration_updated = Signal()

    def __init__(
        self,
        get_active_recording_info: Callable[..., Union[RecordingInfoModel, Path]],
        kill_thread_event: threading.Event,
        gui_state: GuiState,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent=parent)
        self.gui_state = gui_state
        self._has_a_toml_path = False
        self._calibration_toml_path = None
        self._get_active_recording_info = get_active_recording_info
        self._kill_thread_event = kill_thread_event

        self.parent = parent

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._calibration_toml_path = None
        self._kill_thread_event = kill_thread_event

        self._anipose_calibration_frame_worker = None
        self._user_selected_toml_path = None

        self._selected_calibration_toml_label = QLabel("")
        self._selected_calibration_toml_label.setWordWrap(True)

        self._layout.addWidget(self._selected_calibration_toml_label)

        self._radio_button_layout = self._create_radio_button_layout()
        self._radio_button_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.addLayout(self._radio_button_layout)
        # self._layout.addStretch()

    @property
    def calibration_toml_path(self) -> str:
        return self._calibration_toml_path

    @property
    def radio_button_layout(self) -> QLayout:
        return self._radio_button_layout

    def _create_radio_button_layout(self):
        radio_button_form_layout = QFormLayout()

        radio_button_form_layout.addRow(self._create_use_most_recent_calibration_radio_button())

        radio_button_form_layout.addRow(self._create_load_calibration_from_file_radio_button())

        radio_button_form_layout.addRow(self._add_calibrate_from_active_recording_radio_button())

        radio_button_form_layout.addRow(self._create_charuco_options_layout())

        self.update_calibration_toml_path()
        return radio_button_form_layout

    def _create_load_calibration_from_file_radio_button(self) -> QLayout:
        vbox_layout = QVBoxLayout()
        radio_button_push_button_layout = QHBoxLayout()
        vbox_layout.addLayout(radio_button_push_button_layout)

        self._load_calibration_from_file_radio_button = QRadioButton("Load calibration from file")
        radio_button_push_button_layout.addWidget(self._load_calibration_from_file_radio_button)
        self._load_calibration_from_file_radio_button.toggled.connect(self._handle_load_calibration_from_file_toggled)

        self._load_calibration_toml_dialog_button = QPushButton("Load TOML...")
        radio_button_push_button_layout.addWidget(self._load_calibration_toml_dialog_button)
        # self._load_calibration_toml_dialog_button.setStyleSheet("font-size: 10pt;")
        self._load_calibration_toml_dialog_button.clicked.connect(self.open_load_camera_calibration_toml_dialog)
        self._load_calibration_toml_dialog_button.setEnabled(False)

        return vbox_layout

    def update_calibration_toml_path(self, toml_path: str = None):
        active_recording_info = self._get_active_recording_info()
        if toml_path is None and active_recording_info is not None:
            if active_recording_info.single_video_check:
                pass

            elif self._load_calibration_from_file_radio_button.isChecked():
                if self._user_selected_toml_path is not None:
                    toml_path = self._user_selected_toml_path
                else:
                    toml_path = self._check_active_recording_for_calibration_toml()

            elif self._use_most_recent_calibration_radio_button.isChecked():
                toml_path = get_last_successful_calibration_toml_path()

            elif self._calibrate_from_active_recording_radio_button.isChecked():
                toml_path = self._check_active_recording_for_calibration_toml()

            else:  # no button checked -> initialize
                toml_path = self._check_active_recording_for_calibration_toml()
                if toml_path is not None:
                    self._load_calibration_from_file_radio_button.setChecked(True)
                else:
                    toml_path = get_last_successful_calibration_toml_path()
                    self._use_most_recent_calibration_radio_button.setChecked(True)

        self._calibration_toml_path = toml_path

        if self._calibration_toml_path is not None:
            logger.debug(f"Setting calibration TOML path: {self._calibration_toml_path}")
            self._show_selected_calibration_toml_path(self._calibration_toml_path)
        elif active_recording_info is None:
            self._show_selected_calibration_toml_path("-No Active Recording-")
        elif active_recording_info.single_video_check:
            self._show_selected_calibration_toml_path("-Single Video Recording, No Calibration Needed-")
        else:
            self._show_selected_calibration_toml_path("-Calibration File Not Found-")

    def _bring_up_groundplane_calibration_failed_dialog(self, message: str):
        failure_dialog = GroundPlaneCalibrationFailedDialog(message=message)
        failure_dialog.exec()

    def _add_calibrate_from_active_recording_radio_button(self):
        hbox = QHBoxLayout()

        self._calibrate_from_active_recording_radio_button = QRadioButton("Calibrate from Active Recording")
        hbox.addWidget(self._calibrate_from_active_recording_radio_button)

        self._calibrate_from_active_recording_radio_button.toggled.connect(
            self._handle_calibrate_from_active_recording_toggled
        )

        self._calibrate_from_active_recording_button = QPushButton("Run calibration...")
        hbox.addWidget(self._calibrate_from_active_recording_button)

        self._calibrate_from_active_recording_button.setEnabled(False)
        self._calibrate_from_active_recording_button.clicked.connect(self.calibrate_from_active_recording)

        return hbox

    def _create_charuco_options_layout(self):
        vbox = QVBoxLayout()

        hbox1 = QHBoxLayout()
        hbox1.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Square size form layout
        self._charuco_square_size_form_layout = self._create_charuco_square_size_form_layout()
        hbox1.addLayout(self._charuco_square_size_form_layout)

        hbox1.addSpacing(8)

        # Board dropdown + label
        self._board_dropdown_label = QLabel("Charuco Board:")
        self._board_dropdown_label.setStyleSheet("QLabel { font-size: 12px; }")
        self._board_dropdown_label.setEnabled(False)
        self._board_dropdown = self._create_board_dropdown()
        self._board_dropdown.currentTextChanged.connect(self._on_charuco_board_dropdown_changed)
        hbox1.addWidget(self._board_dropdown_label)
        hbox1.addWidget(self._board_dropdown)

        vbox.addLayout(hbox1)

        # Groundplane checkbox row
        hbox2 = QHBoxLayout()
        hbox2.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._use_charuco_as_groundplane_checkbox = QCheckBox(
            "Use initial Charuco board position as groundplane origin"
        )
        self._use_charuco_as_groundplane_checkbox.setStyleSheet("QCheckBox { font-size: 12px; }")
        self._use_charuco_as_groundplane_checkbox.setToolTip(
            "Set the Charuco board's coordinate system as the global origin"
        )
        self._use_charuco_as_groundplane_checkbox.setChecked(False)
        self._use_charuco_as_groundplane_checkbox.setEnabled(False)
        self._use_charuco_as_groundplane_checkbox.setVisible(False)

        hbox2.addWidget(self._use_charuco_as_groundplane_checkbox)
        vbox.addLayout(hbox2)

        # Hide by default
        self._set_charuco_square_size_form_layout_visibility(False)
        self._set_charuco_board_dropdown_visibility(False)

        return vbox

    def _create_use_most_recent_calibration_radio_button(self):
        self._use_most_recent_calibration_radio_button = QRadioButton("Use most recent calibration")

        self._use_most_recent_calibration_radio_button.toggled.connect(self._handle_use_most_recent_calibration_toggled)

        self._use_most_recent_calibration_radio_button.setToolTip(get_last_successful_calibration_toml_path())

        return self._use_most_recent_calibration_radio_button

    def update_calibrate_from_active_recording_button_text(self):
        active_recording_info = self._get_active_recording_info()
        if active_recording_info is None:
            active_path_str = "- No active recording selected -"
        else:
            if not active_recording_info.synchronized_videos_status_check:
                active_path_str = f"Recording: {active_recording_info.name} has no synchronized videos!"
            elif active_recording_info.single_video_check:
                active_path_str = "Single Video Recording: No calibration needed"
            else:
                active_path_str = f"Calibrate from Recording: {self._get_active_recording_info().name}"

        self._calibrate_from_active_recording_button.setToolTip(active_path_str)

    def _handle_use_most_recent_calibration_toggled(self, checked):
        self.update_calibration_toml_path()

    def _handle_load_calibration_from_file_toggled(self, checked):
        if checked:
            self._load_calibration_toml_dialog_button.setEnabled(True)
        else:
            self._load_calibration_toml_dialog_button.setEnabled(False)

        self.update_calibration_toml_path()

    def _handle_calibrate_from_active_recording_toggled(self, checked):
        active_recording_info = self._get_active_recording_info()
        self.update_calibrate_from_active_recording_button_text()
        self.update_calibration_toml_path()

        if checked and active_recording_info is not None and active_recording_info.synchronized_videos_status_check:
            self._calibrate_from_active_recording_button.setEnabled(True)
            self._set_charuco_square_size_form_layout_visibility(True)
            self._use_charuco_as_groundplane_checkbox.setEnabled(True)
            self._use_charuco_as_groundplane_checkbox.setVisible(True)
            self._set_charuco_board_dropdown_visibility(True)
        else:
            self._calibrate_from_active_recording_button.setEnabled(False)
            self._set_charuco_square_size_form_layout_visibility(False)
            self._use_charuco_as_groundplane_checkbox.setEnabled(False)
            self._use_charuco_as_groundplane_checkbox.setVisible(False)
            self._set_charuco_board_dropdown_visibility(False)

    def _set_charuco_square_size_form_layout_visibility(self, visible):
        label_index = self._charuco_square_size_form_layout.indexOf(self._charuco_square_size_label)
        line_edit_index = self._charuco_square_size_form_layout.indexOf(self._charuco_square_size_line_edit)
        if visible:
            self._charuco_square_size_form_layout.itemAt(label_index).widget().setEnabled(True)
            self._charuco_square_size_form_layout.itemAt(line_edit_index).widget().setEnabled(True)
            self._charuco_square_size_form_layout.itemAt(label_index).widget().setVisible(True)
            self._charuco_square_size_form_layout.itemAt(line_edit_index).widget().setVisible(True)
        else:
            self._charuco_square_size_form_layout.itemAt(label_index).widget().setEnabled(False)
            self._charuco_square_size_form_layout.itemAt(line_edit_index).widget().setEnabled(False)
            self._charuco_square_size_form_layout.itemAt(label_index).widget().setVisible(False)
            self._charuco_square_size_form_layout.itemAt(line_edit_index).widget().setVisible(False)

    def _set_charuco_board_dropdown_visibility(self, visible: bool):
        self._board_dropdown.setEnabled(visible)
        self._board_dropdown_label.setEnabled(visible)
        self._board_dropdown.setVisible(visible)
        self._board_dropdown_label.setVisible(visible)

    def open_load_camera_calibration_toml_dialog(self) -> str:
        # from this tutorial - https://www.youtube.com/watch?v=gg5TepTc2Jg&t=649s
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)

        calibration_toml_path_selection = dialog.getOpenFileName(
            self,
            "Select 'toml' containing camera calibration info",
            str(self._get_active_recording_info().path),
            "Camera Calibration TOML (*.toml)",
        )
        if len(calibration_toml_path_selection) > 0:
            self._user_selected_toml_path = calibration_toml_path_selection[0]
            logger.info(f"User selected camera calibration toml path:{self._user_selected_toml_path}")
            self._show_selected_calibration_toml_path(self._user_selected_toml_path)
            self.update_calibration_toml_path(toml_path=self._user_selected_toml_path)
            return self._user_selected_toml_path

    def _show_selected_calibration_toml_path(self, calibration_toml_path_str: str):
        self._calibration_toml_path = calibration_toml_path_str
        path = calibration_toml_path_str.replace(os.sep, "/ ")
        self._selected_calibration_toml_label.setText(path)
        self._selected_calibration_toml_label.show()

    def _create_charuco_square_size_form_layout(self):
        charuco_square_size_form_layout = QFormLayout()

        self._charuco_square_size_line_edit = QLineEdit()
        self._charuco_square_size_line_edit.setValidator(QDoubleValidator())
        self._charuco_square_size_line_edit.setFixedWidth(65)

        self._charuco_square_size_label = QLabel("Charuco square size (mm)")
        self._charuco_square_size_label.setStyleSheet("QLabel { font-size: 12px;  }")

        self._charuco_square_size_line_edit.setText(str(self.gui_state.charuco_square_size))
        self._charuco_square_size_line_edit.setToolTip(
            "The length of one of the edges of the black squares in the calibration board in mm"
        )
        self._charuco_square_size_line_edit.textEdited.connect(self._on_charuco_square_size_line_edit_changed)
        charuco_square_size_form_layout.addRow(self._charuco_square_size_label, self._charuco_square_size_line_edit)
        charuco_square_size_form_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        return charuco_square_size_form_layout

    def _create_board_dropdown(self) -> QComboBox:
        board_dropdown = QComboBox()
        board_dropdown.setToolTip("Select the Charuco board to use for calibration")
        board_dropdown.setFixedWidth(130)
        board_dropdown.setStyleSheet("QComboBox { font-size: 12px; }")
        board_dropdown.setEnabled(False)
        board_dropdown.setEditable(False)
        board_dropdown.addItems(list(CHARUCO_BOARDS.keys()))
        return board_dropdown

    def _on_charuco_square_size_line_edit_changed(self):
        try:
            self.gui_state.charuco_square_size = float(self._charuco_square_size_line_edit.text())
        except ValueError:
            return
        save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())
        self.control_panel_calibration_updated.emit()

    def _on_charuco_board_dropdown_changed(self):
        selected_board_name = self._board_dropdown.currentText()
        self.gui_state.charuco_board_name = selected_board_name
        save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())
        self.control_panel_calibration_updated.emit()

    @Slot()
    def charuco_option_updated(self):
        self.gui_state = load_gui_state(file_pathstring=get_gui_state_json_path())
        self._board_dropdown.setCurrentText(self.gui_state.charuco_board_name)
        self._charuco_square_size_line_edit.setText(str(self.gui_state.charuco_square_size))

    @Slot(str)
    def _log_calibration_progress_callbacks(self, message: str):
        logger.info(message)

    def calibrate_from_active_recording(
        self,
        charuco_square_size_mm: float = None,
        use_charuco_as_groundplane: bool = None,
        charuco_board_name: str = None,
    ):
        if not charuco_square_size_mm:
            charuco_square_size_mm = float(self._charuco_square_size_line_edit.text())

        if not use_charuco_as_groundplane:
            use_charuco_as_groundplane = self._use_charuco_as_groundplane_checkbox.isChecked()

        if not charuco_board_name:
            charuco_board_name = self._board_dropdown.currentText()

        charuco_board_definition = CHARUCO_BOARDS[charuco_board_name]()

        active_recording_info = self._get_active_recording_info()
        if active_recording_info is None:
            logger.error("Cannot calibrate from active recording - no active recording selected")
            return

        logger.info(f"Calibrating from active recording: {active_recording_info.name}")

        if not active_recording_info.synchronized_videos_status_check:
            logger.error(
                f"Cannot calibrate from {active_recording_info.name} -"
                f" `active_recording_info.synchronized_videos_status_check` is "
                f"{active_recording_info.synchronized_videos_status_check}"
            )

            return

        self._anipose_calibration_frame_worker = AniposeCalibrationThreadWorker(
            calibration_videos_folder_path=active_recording_info.synchronized_videos_folder_path,
            charuco_square_size=float(charuco_square_size_mm),
            use_charuco_as_groundplane=use_charuco_as_groundplane,
            charuco_board_definition=charuco_board_definition,
            kill_thread_event=self._kill_thread_event,
        )

        self._anipose_calibration_frame_worker.start()

        self._anipose_calibration_frame_worker.in_progress.connect(self._log_calibration_progress_callbacks)

        self._anipose_calibration_frame_worker.finished.connect(self.update_calibration_toml_path)

        self._anipose_calibration_frame_worker.groundplane_failed.connect(
            self._bring_up_groundplane_calibration_failed_dialog
        )

    def _check_active_recording_for_calibration_toml(self):
        active_rec = self._get_active_recording_info()
        if active_rec is not None:
            if active_rec.calibration_toml_check:
                return self._get_active_recording_info().calibration_toml_path


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = CalibrationControlPanel()
    widget.show()
    sys.exit(app.exec())
