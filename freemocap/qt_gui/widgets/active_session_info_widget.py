import logging
from pathlib import Path
from typing import List, Union

from PyQt6.QtCore import pyqtSignal, QFileSystemWatcher
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget
from pyqtgraph.parametertree import Parameter, ParameterTree

from freemocap.core_processes.session_processing_parameter_models.session_recording_info.recording_info_model import (
    RecordingInfoModel,
)

from freemocap.core_processes.session_processing_parameter_models.session_processing_parameter_models import (
    SessionInfoModel,
)

logger = logging.getLogger(__name__)


class ActiveSessionInfoWidget(QFileSystemWatcher):
    directory_changed_signal = pyqtSignal(str)

    def __init__(self, session_path: Union[str, Path], parent=None):
        super().__init__(parent=parent)
        self.addPath(session_path)
        self.directoryChanged.connect(self.directory_changed_signal.emit)


class ActiveSessionWidget(QWidget):
    new_active_recording_selected_signal = pyqtSignal(str)

    def __init__(
        self,
        session_info_model: SessionInfoModel = SessionInfoModel(),
        parent: QWidget = None,
    ):
        super().__init__(parent=parent)

        self._session_info_model = session_info_model

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._parameter_tree_widget = ParameterTree(parent=self, showHeader=False)
        self._layout.addWidget(self._parameter_tree_widget)

        self._setup_parameter_tree(self._session_info_model)

        self._parameter_tree_widget.doubleClicked.connect(
            self._handle_double_click_event
        )

        self._active_session_directory_watcher = (
            self._create_active_session_directory_watcher(
                self._session_info_model.session_folder_path
            )
        )

    def _setup_parameter_tree(self, session_info_model: SessionInfoModel):
        self._parameter_tree_widget.clear()
        self._parameter_tree_widget.setParameters(
            self._create_parameter_tree(session_info_model)
        )

    def _create_parameter_tree(self, session_info_model: SessionInfoModel):
        available_recordings = self._get_available_recordings()

        active_session_parameter = Parameter.create(
            name="Session Name: " + Path(session_info_model.session_folder_path).name,
            type="group",
            children=[
                dict(
                    name="Path",
                    type="str",
                    value=session_info_model.session_folder_path,
                    readonly=True,
                ),
                self._create_recording_parameter_group(available_recordings),
            ],
        )

        return active_session_parameter

    def _get_available_recordings(self) -> List[Union[str, Path]]:
        available_recordings = [
            recording
            for recording in Path(
                self._session_info_model.session_folder_path
            ).iterdir()
            if recording.is_dir()
        ]
        if (
            len(available_recordings) > 0
            and self._session_info_model.recording_info_model is None
        ):
            self._session_info_model.set_recording_info(
                recording_folder_path=available_recordings[-1]
            )
        return available_recordings

    def _create_recording_parameter_group(
        self, available_recordings: List[Union[str, Path]]
    ):
        self._recording_parameters_list = [
            self._create_recording_status_parameter_tree(
                RecordingInfoModel(recording_path)
            )
            for recording_path in available_recordings
        ]
        return Parameter.create(
            name="Available Recordings",
            type="group",
            collapsed=True,
            children=self._recording_parameters_list,
        )

    def _create_recording_status_parameter_tree(
        self, recording_info_model: RecordingInfoModel
    ):
        parameter_group = Parameter.create(
            name=f"Recording Name: {recording_info_model.name}",
            type="group",
            readonly=True,
            children=[
                dict(
                    name="Path",
                    type="str",
                    value=recording_info_model.path,
                    readonly=True,
                ),
                dict(
                    name="Calibration TOML",
                    type="str",
                    value=recording_info_model.calibration_toml_file_path,
                    readonly=True,
                ),
                dict(
                    name="Status",
                    type="group",
                    readonly=True,
                    children=[
                        dict(
                            name="Synchronized Videos Recorded",
                            type="str",
                            value=recording_info_model.synchronized_videos_exist,
                            readonly=True,
                        ),
                        dict(
                            name="2D data exists?",
                            type="str",
                            value=recording_info_model.data2d_exists,
                            readonly=True,
                        ),
                        dict(
                            name="3D data exists?",
                            type="str",
                            value=recording_info_model.data3d_exists,
                            readonly=True,
                        ),
                        dict(
                            name="Center-of-Mass data exists?",
                            type="str",
                            value=recording_info_model.center_of_mass_data_exists,
                            readonly=True,
                        ),
                    ],
                ),
            ],
        )

        return parameter_group

    def _handle_double_click_event(self, a0: QMouseEvent) -> None:
        paremeter_item = self._parameter_tree_widget.itemFromIndex(
            self._parameter_tree_widget.currentIndex()
        )[0]
        logger.info(
            f"Double clicked on Parameter Item named: {paremeter_item.param.name()}"
        )
        parent = paremeter_item()
        while parent is not None:
            if "Recording Name:" in parent.param.name():
                logger.info(f"Found Recording Name: {parent.param.name()}")
                self.set_active_recording(parent.param.child("Path").value())
                break
            else:
                parent = parent.parent()
        print("done")

    def set_active_recording(self, recording_folder_path: Union[str, Path]):
        self._clear_active_recording_name()
        for recording_parameter in self._recording_parameters_list:
            if recording_parameter.child("Path").value() == recording_folder_path:
                recording_parameter.setName(
                    f"Recording Name: {Path(recording_folder_path).name} (Active)"
                )
                self._session_info_model.set_recording_info(
                    recording_folder_path=recording_folder_path,
                    calibration_toml_path=recording_parameter.child(
                        "Calibration TOML"
                    ).value(),
                )

                self.new_active_recording_selected_signal.emit(
                    str(recording_folder_path)
                )
                return

        logger.info(f"Setting active recording to {recording_folder_path}")
        self._session_info_model.recording_folder_path = str(recording_folder_path)

    def _clear_active_recording_name(self):
        for recording_parameter in self._recording_parameters_list:
            recording_parameter.setName(
                f"Recording Name: {Path(recording_parameter.child('Path').value()).name}"
            )

    def _create_active_session_directory_watcher(
        self, session_folder_path: Union[str, Path]
    ):
        active_session_directory_watcher = QFileSystemWatcher()
        active_session_directory_watcher.addPath(session_folder_path)
        active_session_directory_watcher.directoryChanged.connect(
            self._handle_directory_changed
        )
        return active_session_directory_watcher

    def _handle_directory_changed(self, path: str):
        logger.info(f"Directory changed: {path} - Updating Parameter Tree")
        self._setup_parameter_tree(self._session_info_model)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    active_session_widget = ActiveSessionWidget(
        session_info_model=SessionInfoModel(use_most_recent=True)
    )
    active_session_widget.show()
    sys.exit(app.exec())
