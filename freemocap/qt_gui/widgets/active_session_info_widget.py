import logging
from pathlib import Path
from typing import List, Union

from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget
from pyqtgraph.parametertree import Parameter, ParameterTree

from freemocap.core_processes.session_processing_parameter_models.session_processing_parameter_models import (
    SessionInfoModel,
)

logger = logging.getLogger(__name__)


class ActiveSessionWidget(QWidget):
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

        self._parameter_tree_widget.setParameters(
            self._create_parameter_tree(self._session_info_model)
        )

        self._parameter_tree_widget.doubleClicked.connect(
            self._handle_double_click_event
        )

    def set_session_info(self, session_info_model: SessionInfoModel):
        self._session_info_model = session_info_model
        self._create_parameter_tree(self._session_info_model)

    def _create_parameter_tree(self, session_info_model: SessionInfoModel):
        available_recordings = self._get_available_recordings(session_info_model)

        active_session_parameter = Parameter.create(
            name="Active Session",
            type="group",
            children=[
                dict(
                    name="Session Name",
                    type="str",
                    value=session_info_model.session_name,
                    readonly=True,
                ),
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

    def _get_available_recordings(
        self, session_info_model: SessionInfoModel
    ) -> List[Union[str, Path]]:
        return [
            str(recording)
            for recording in Path(session_info_model.session_folder_path).iterdir()
            if recording.is_dir()
        ]

    def _create_recording_parameter_group(
        self, available_recordings: List[Union[str, Path]]
    ):
        self._recording_parameters_list = [
            self._create_recording_status_parameter_tree(recording_path)
            for recording_path in available_recordings
        ]
        return Parameter.create(
            name="Available Recordings",
            type="group",
            collapsed=True,
            children=self._recording_parameters_list,
        )

    def _create_recording_status_parameter_tree(self, recording_path: Union[str, Path]):
        return Parameter.create(
            name=f"Recording Name: {Path(recording_path).name}",
            type="group",
            readonly=True,
            children=[
                dict(
                    name="Path",
                    type="str",
                    value=recording_path,
                    readonly=True,
                ),
                dict(
                    name="Status",
                    type="group",
                    readonly=True,
                    children=[
                        dict(
                            name="Calibration TOML",
                            type="str",
                            value=RecordingFolderStatus(
                                recording_path
                            ).calibration_toml_exists,
                        ),
                        dict(
                            name="Synchronized Videos Recorded",
                            type="str",
                            value=RecordingFolderStatus(
                                recording_path
                            ).synchronized_videos_exist_bool,
                            readonly=True,
                        ),
                        dict(
                            name="2D Tracking Completed",
                            type="str",
                            value=RecordingFolderStatus(
                                recording_path
                            ).data2d_exists_bool,
                            readonly=True,
                        ),
                        dict(
                            name="3D Reconstruction Completed",
                            type="str",
                            value=RecordingFolderStatus(
                                recording_path
                            ).data3d_exists_bool,
                            readonly=True,
                        ),
                        dict(
                            name="Post Processing Completed",
                            type="str",
                            value=RecordingFolderStatus(
                                recording_path
                            ).post_processed_data_exists_bool,
                            readonly=True,
                        ),
                    ],
                ),
            ],
        )

    def _handle_double_click_event(self, a0: QMouseEvent) -> None:
        paremeter_item = self._parameter_tree_widget.itemFromIndex(
            self._parameter_tree_widget.currentIndex()
        )[0]
        logger.info(
            f"Double clicked on Parameter Item named: {paremeter_item.param.name()}"
        )
        parent = paremeter_item.parent()
        while parent is not None:
            if "Recording Name:" in parent.param.name():
                logger.info(f"Found Recording Name: {parent.param.name()}")
                self._set_active_recording(parent.param.child("Path").value())
                break
            else:
                parent = parent.parent()
        print("done")

    def _set_active_recording(self, recording_folder_path: Union[str, Path]):
        self._clear_active_recording_name()
        for recording_parameter in self._recording_parameters_list:
            if recording_parameter.child("Path").value() == recording_folder_path:
                recording_parameter.setName(
                    f"Recording Name: {Path(recording_folder_path).name} (Active)"
                )

        logger.info(f"Setting active recording to {recording_folder_path}")
        self._session_info_model.recording_folder_path = str(recording_folder_path)

    def _clear_active_recording_name(self):
        for recording_parameter in self._recording_parameters_list:
            recording_parameter.setName(
                f"Recording Name: {Path(recording_parameter.child('Path').value()).name}"
            )


class RecordingFolderStatus:
    def __init__(self, recording_path: Union[str, Path]):
        self.recording_path = recording_path
        self.calibration_toml_exists = self._check_calibration_toml_exists()
        self.synchronized_videos_exist_bool = self._check_synchronized_videos_exist()
        self.data2d_exists_bool = self._check_data2d_exists()
        self.data3d_exists_bool = self._check_data3d_exists()
        self.post_processed_data_exists_bool = self._check_post_processed_data_exists()

    def _check_synchronized_videos_exist(self) -> bool:
        return False

    def _check_data2d_exists(self) -> bool:
        return False

    def _check_data3d_exists(self) -> bool:
        return False

    def _check_post_processed_data_exists(self) -> bool:
        return False

    def _check_calibration_toml_exists(self):
        return False


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    active_session_widget = ActiveSessionWidget()
    active_session_widget.show()
    sys.exit(app.exec())
