import logging
from typing import Callable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget
from pyqtgraph.parametertree import Parameter, ParameterTree

from freemocap.core_processes.session_processing_parameter_models.session_processing_parameter_models import (
    SessionProcessingParameterModel,
)
from freemocap.qt_gui.sub_widgets.process_mocap_data_panel.parameter_groups.create_3d_triangulation_parameter_group import (
    create_3d_triangulation_prarameter_group,
)
from freemocap.qt_gui.sub_widgets.process_mocap_data_panel.parameter_groups.create_mediapipe_parameter_group import (
    create_mediapipe_parameter_group,
)
from freemocap.qt_gui.sub_widgets.process_mocap_data_panel.parameter_groups.create_post_processing_parameter_group import (
    create_post_processing_parameter_group,
)
from freemocap.qt_gui.workers.process_motion_capture_data_thread_worker import (
    ProcessMotionCaptureDataThreadWorker,
)

logger = logging.getLogger(__name__)


class ProcessMotionCaptureDataPanel(QWidget):
    begin_processing_signal = pyqtSignal(dict)

    def __init__(
        self,
        session_processing_parameters: SessionProcessingParameterModel,
        parent=None,
    ):
        super().__init__(parent=parent)

        self._session_processing_parameters = session_processing_parameters

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._process_motion_capture_data = QPushButton(
            "Process Motion Capture Videos",
        )
        self._process_motion_capture_data.clicked.connect(
            self._launch_process_motion_capture_data_process
        )
        self._layout.addWidget(self._process_motion_capture_data)

        self._parameter_tree_widget = ParameterTree(parent=self, showHeader=False)
        self._layout.addWidget(self._parameter_tree_widget)

        self._add_parameters_to_parameter_tree_widget(
            self._parameter_tree_widget,
            session_processing_parameter_model=self._session_processing_parameters,
        )

    def _add_parameters_to_parameter_tree_widget(
        self,
        parameter_tree_widget: ParameterTree,
        session_processing_parameter_model: SessionProcessingParameterModel,
    ):
        parameter_group = (
            self._convert_session_processing_parameter_model_to_parameter_group(
                session_processing_parameter_model
            )
        )
        parameter_tree_widget.setParameters(parameter_group, showTop=False)

        return parameter_group

    def _convert_session_processing_parameter_model_to_parameter_group(
        self,
        parameters: SessionProcessingParameterModel = SessionProcessingParameterModel(),
    ):

        parameter_group = Parameter.create(
            name="Processing Parameters",
            type="group",
            children=[
                dict(
                    name="2d Image Trackers",
                    type="group",
                    children=[
                        self._create_new_skip_this_step_parameter(),
                        create_mediapipe_parameter_group(
                            parameters.mediapipe_parameters
                        ),
                    ],
                    tip="Methods for tracking 2d points in images (e.g. mediapipe, deeplabcut(TODO), openpose(TODO), etc ...)",
                ),
                dict(
                    name="3d triangulation methods",
                    type="group",
                    children=[
                        self._create_new_skip_this_step_parameter(),
                        create_3d_triangulation_prarameter_group(
                            parameters.anipose_triangulate_3d_parameters
                        ),
                    ],
                    tip="Methods for triangulating 3d points from 2d points (using epipolar geometry and the 'camera_calibration' data).",
                ),
                dict(
                    name="Post Processing (data cleaning)",
                    type="group",
                    children=[
                        self._create_new_skip_this_step_parameter(),
                        create_post_processing_parameter_group(
                            parameters.post_processing_parameters
                        ),
                    ],
                    tip="Methods for cleaning up the data (e.g. filtering/smoothing, gap filling, etc ...)"
                    "TODO - Add/expose more post processing methods here (e.g. gap filling, outlier removal, etc ...)",
                ),
            ],
        )
        return parameter_group

    def _extract_session_parameter_model_from_parameter_tree(
        self,
    ) -> SessionProcessingParameterModel:
        session_parameter_model = SessionProcessingParameterModel()

        logger.debug(
            "TODO - extract the parameter values from the parameter tree and populate the session_parameter_model. Just using defaults for now."
        )
        return session_parameter_model

    def _create_new_skip_this_step_parameter(self):
        parameter = Parameter.create(
            name="Skip this step?",
            type="bool",
            value=False,
            tip="If you have already run this step, you can skip it."
            "re-running it will overwrite the existing data.",
        )
        parameter.sigValueChanged.connect(self.disable_this_parameter_group)

        return parameter

    def disable_this_parameter_group(self, parameter, changes):
        logger.debug(
            f"TODO - disable parameter group when 'skip this step?' is checked"
        )
        pass
        # skip_this_step_bool = parameter.value()
        # parameter_group = parameter.parent()
        # for child in parameter_group.children():
        #     if child.name() != "Skip this step?":
        #         logger.debug(f"Disabling {child.name()}")
        #         child.setOpts(enabled=not skip_this_step_bool)

    def _launch_process_motion_capture_data_process(self):
        logger.debug("Launching process motion capture data process")
        session_parameter_model = (
            self._extract_session_parameter_model_from_parameter_tree()
        )

        self._process_motion_capture_data_thread_worker = (
            ProcessMotionCaptureDataThreadWorker(session_parameter_model)
        )
        self._process_motion_capture_data_thread_worker.start()


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    window = ProcessMotionCaptureDataPanel()
    window.show()
    app.exec()
