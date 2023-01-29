import logging
from pathlib import Path
from typing import List, Union

from PyQt6.QtCore import pyqtSignal, QFileSystemWatcher
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget
from pyqtgraph.parametertree import Parameter, ParameterTree

from freemocap.configuration.paths_and_files_names import (
    get_most_recent_recording_path,
)
from freemocap.parameter_info_models.recording_info_model import (
    RecordingInfoModel,
)
from freemocap.parameter_info_models.session_info_model import (
    SessionInfoModel,
)

logger = logging.getLogger(__name__)


class ActiveRecordingInfoWidget(QWidget):
    new_active_recording_selected_signal = pyqtSignal(RecordingInfoModel)

    def __init__(
        self,
        active_recording_info: RecordingInfoModel = None,
        parent: QWidget = None,
    ):
        super().__init__(parent=parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._active_recording_info = active_recording_info
        self._directory_watcher = self._create_directory_watcher()

        self._active_recording_view_widget = ActiveRecordingTreeView(parent=self)
        self._layout.addWidget(self._active_recording_view_widget)

    @property
    def active_recording_info(self):
        return self._active_recording_info

    @property
    def active_recording_view_widget(self):
        return self._active_recording_view_widget

    def get_active_recording_info(self, return_path: bool = False):
        # this is redundant to the `active_recording_info` property,
        # but it will be more intuitive to send this down as a callable
        # rather than relying on 'pass-by-reference' magic lol
        if self._active_recording_info is None:
            self.set_active_recording(recording_folder_path=get_most_recent_recording_path())

        if return_path:
            return self._active_recording_info.path

        return self._active_recording_info

    def set_active_recording(
        self,
        recording_folder_path: Union[str, Path],
    ):
        logger.info(f"Setting active recording to {recording_folder_path}")
        self._active_recording_info = RecordingInfoModel(recording_folder_path=str(recording_folder_path))

        self._update_file_watch_path(folder_to_watch=recording_folder_path)

        self._active_recording_view_widget.setup_parameter_tree(self._active_recording_info)

        self.new_active_recording_selected_signal.emit(self._active_recording_info)

    def _update_file_watch_path(self, folder_to_watch: Union[str, Path]):
        logger.debug(f"Updating file watch path to: {folder_to_watch}")

        if self._directory_watcher.directories():
            logger.debug(f"Removing path from watch list: {self._directory_watcher.directories()}")

        self._directory_watcher.removePaths(self._directory_watcher.directories())
        self._directory_watcher.addPath(folder_to_watch)

    def _create_directory_watcher(self):

        directory_watcher = QFileSystemWatcher()
        directory_watcher.directoryChanged.connect(self._handle_directory_changed)
        return directory_watcher

    def _handle_directory_changed(self, path: str):
        logger.info(f"Directory changed: {path} - Updating Parameter Tree")
        self._active_recording_view_widget.setup_parameter_tree(self.active_recording_info)


class ActiveRecordingTreeView(ParameterTree):
    def __init__(self, parent=None):
        super().__init__(parent=parent, showHeader=False)

    def setup_parameter_tree(
        self,
        recording_info_model: RecordingInfoModel,
    ):
        logger.debug(f"Setting up `ActiveRecordingTreeView` for recording: {recording_info_model.name}")
        self.clear()
        self.setParameters(
            self._create_recording_status_parameter_tree(recording_info_model=recording_info_model),
        )

    def update_active_recording_name(self, active_recording_folder_path: Union[str, Path]):
        self._clear_active_recording_name()
        for recording_parameter in self._recording_parameter_trees_list:
            if recording_parameter.child("Path").value() == active_recording_folder_path:
                recording_parameter.setName(f"Recording Name: {Path(active_recording_folder_path).name} (Active)")
                self._active_session_info.set_recording_info(
                    recording_folder_path=active_recording_folder_path,
                    calibration_toml_path=recording_parameter.child("Calibration TOML").value(),
                )

    def _clear_active_recording_name(self):
        for recording_parameter in self._recording_parameter_trees_list:
            recording_parameter.setName(f"Recording Name: {Path(recording_parameter.child('Path').value()).name}")

    def _create_parameter_tree(
        self,
        recording_info_model: RecordingInfoModel,
    ) -> Parameter:

        active_session_parameter = Parameter.create(
            name="Recording Name: " + Path(recording_info_model.path).name,
            type="group",
            children=[
                dict(
                    name="Parent Path",
                    type="str",
                    value=Path(recording_info_model.path).parent,
                    readonly=True,
                ),
                self._create_recording_status_parameter_tree(recording_info_model=recording_info_model),
            ],
        )

        return active_session_parameter

    def _get_available_recordings(self, session_info_model: SessionInfoModel) -> List[Union[str, Path]]:
        try:
            return [
                recording for recording in Path(session_info_model.session_folder_path).iterdir() if recording.is_dir()
            ]
        except Exception as e:
            logger.error(e)
            return []

    def _create_recording_parameter_group(self, available_recordings: List[Union[str, Path]]):

        if len(available_recordings) == 0:
            self._recording_parameter_trees_list = Parameter.create(
                name="No Recordings Found - Either select one in the `File View` window or Record/Import new videos to continue \U0001F4AB",
                type="group",
                readonly=True,
            )
        else:
            self._recording_parameter_trees_list = [
                self._create_recording_status_parameter_tree(RecordingInfoModel(recording_path))
                for recording_path in available_recordings
            ]
        return Parameter.create(
            name="Available Recordings",
            type="group",
            collapsed=True,
            children=self._recording_parameter_trees_list,
        )

    def _create_recording_status_parameter_tree(self, recording_info_model: RecordingInfoModel):
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
                            value=recording_info_model.synchronized_videos_status_check,
                            readonly=True,
                        ),
                        dict(
                            name="2D data exists?",
                            type="str",
                            value=recording_info_model.data2d_status_check,
                            readonly=True,
                        ),
                        dict(
                            name="3D data exists?",
                            type="str",
                            value=recording_info_model.data3d_status_check,
                            readonly=True,
                        ),
                        dict(
                            name="Center-of-Mass data exists?",
                            type="str",
                            value=recording_info_model.center_of_mass_data_status_check,
                            readonly=True,
                        ),
                        dict(
                            name="Blender scene file exists?",
                            type="str",
                            value=recording_info_model.blender_file_status_check,
                            readonly=True,
                        ),
                    ],
                ),
            ],
        )

        return parameter_group


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    active_recording_widget = ActiveRecordingInfoWidget()
    active_recording_widget.show()
    sys.exit(app.exec())
