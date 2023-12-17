import logging
import multiprocessing
import threading
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget, QGroupBox, QPushButton
from pyqtgraph.parametertree import Parameter, ParameterTree

from experimental.process_recording_parameter_tree_widget.calibration_picker_widget import CalibrationPickerWidget
from freemocap.data_layer.recording_models.post_processing_parameter_models import (
    ProcessingParameterModel,
)
from freemocap.gui.qt.widgets.control_panel.process_mocap_data_panel.parameter_groups.create_parameter_groups import (
    create_mediapipe_parameter_group,
    create_3d_triangulation_prarameter_group,
    create_post_processing_parameter_group,
    extract_parameter_model_from_parameter_tree,
    RUN_IMAGE_TRACKING_NAME,
    RUN_3D_TRIANGULATION_NAME,
    RUN_BUTTERWORTH_FILTER_NAME,
    NUMBER_OF_PROCESSES_PARAMETER_NAME,
)
from freemocap.gui.qt.workers.process_motion_capture_data_thread_worker import (
    ProcessMotionCaptureDataThreadWorker,
)

logger = logging.getLogger(__name__)


class ProcessRecordingParameterTreeWidget(ParameterTree):
    def __init__(self,
                 recording_processing_parameter_model: ProcessingParameterModel = ProcessingParameterModel(),
                 parent=None,
                 showHeader=False):
        super().__init__(parent=parent, showHeader=showHeader)
        self.recording_processing_parameter_model = recording_processing_parameter_model
        self.parameter_group = self._generate_parameter_group()
        self.setParameters(self.parameter_group, showTop=False)
        self.setObjectName("parameter-tree-widget")

    def _generate_parameter_group(
            self,
    ):
        return Parameter.create(
            name="Processing Parameters",
            type="group",
            children=[
                dict(
                    name="2d Image Trackers",
                    type="group",
                    children=[
                        self._create_new_run_this_step_parameter(run_step_name=RUN_IMAGE_TRACKING_NAME),
                        self._create_num_processes_parameter(),
                        create_mediapipe_parameter_group(
                            self.recording_processing_parameter_model.mediapipe_parameters_model),
                    ],
                    tip="Methods for tracking 2d points in images (e.g. mediapipe, deeplabcut(TODO), openpose(TODO), etc ...)",
                ),
                dict(
                    name="3d Triangulation Methods",
                    type="group",
                    children=[
                        self._create_new_run_this_step_parameter(run_step_name=RUN_3D_TRIANGULATION_NAME),
                        create_3d_triangulation_prarameter_group(
                            self.recording_processing_parameter_model.anipose_triangulate_3d_parameters_model
                        ),
                    ],
                    tip="Methods for triangulating 3d points from 2d points (using epipolar geometry and the 'camera_calibration' data).",
                ),
                dict(
                    name="Post Processing (data cleaning)",
                    type="group",
                    children=[
                        self._create_new_run_this_step_parameter(run_step_name=RUN_BUTTERWORTH_FILTER_NAME),
                        create_post_processing_parameter_group(
                            self.recording_processing_parameter_model.post_processing_parameters_model
                        ),
                    ],
                    tip="Methods for cleaning up the data (e.g. filtering/smoothing, gap filling, etc ...)"
                        "TODO - Add/expose more post processing methods here (e.g. gap filling, outlier removal, etc ...)",
                ),
            ],
        )

    def extract_recording_parameter_model(
            self,
    ) -> ProcessingParameterModel:
        recording_processing_parameter_model = extract_parameter_model_from_parameter_tree(
            parameter_object=self.parameter_group
        )

        return recording_processing_parameter_model

    def _create_new_run_this_step_parameter(self, run_step_name: str):
        parameter = Parameter.create(
            name=run_step_name,
            type="bool",
            value=True,
            tip="If you have already run this step, you can skip it." "re-running it will overwrite the existing data.",
        )
        parameter.sigValueChanged.connect(self.enable_this_parameter_group)

        return parameter

    def _create_num_processes_parameter(self):
        parameter = Parameter.create(
            name=NUMBER_OF_PROCESSES_PARAMETER_NAME,
            type="int",
            value=(multiprocessing.cpu_count() - 1),
            tip="If your computer has issues processing larger videos, you can try setting number of processes to 1 to process each video serially.",
        )
        return parameter

    def enable_this_parameter_group(self, parameter):
        run_this_step_bool = parameter.value()
        parameter_group = parameter.parent()
        for child in parameter_group.children():
            if child.name().split(" ")[0] != "Run":
                logger.debug(
                    f"{'Enabling' if run_this_step_bool else 'Disabling'} {child.name()} in processing pipeline"
                )
                self.set_parameter_enabled(child, run_this_step_bool)

    def set_parameter_enabled(self, parameter, enabled_bool):
        parameter.setOpts(enabled=enabled_bool)
        if parameter.hasChildren():
            for child in parameter.children():
                self.set_parameter_enabled(child, enabled_bool)


class BatchProcessRecodingControlPanel(QWidget):
    def __init__(
            self,
            process_recording_parameter_model: ProcessingParameterModel = ProcessingParameterModel(),
            parent=None,
    ):
        super().__init__(parent=parent)
        self._recording_processing_parameter_model = process_recording_parameter_model
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self.initUI()

    def initUI(self):
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._create_calibration_group_box()
        self._create_process_parameters_widget()
        self._punch_it_button = QPushButton("Punch it!")
        self._punch_it_button.clicked.connect(self._launch_process_motion_capture_data_thread_worker)
        self._layout.addWidget(self._punch_it_button)

    def _create_calibration_group_box(self):
        self._calibration_picker_widget = CalibrationPickerWidget(
            parent=self,
        )
        calibration_group_box = QGroupBox("Selected Capture Volume Calibration TOML:")
        vbox = QVBoxLayout()
        calibration_group_box.setLayout(vbox)
        self._layout.addWidget(calibration_group_box)
        vbox.addWidget(self._calibration_picker_widget)

    def _create_process_parameters_widget(self):
        self._parameter_tree_widget = ProcessRecordingParameterTreeWidget()
        self._layout.addWidget(self._parameter_tree_widget)

    def _launch_process_motion_capture_data_thread_worker(self):
        logger.debug("Launching process motion capture data process")
        recording_parameter_model = self._parameter_tree_widget.extract_recording_parameter_model()

        if not Path(recording_parameter_model.recording_path).exists() or recording_parameter_model.recording_path == "":
            raise FileNotFoundError( f"Recording path does not exist: {recording_parameter_model.recording_path}.")

        self._get_calibration_toml_path(recording_parameter_model)

        self._process_motion_capture_data_thread_worker = ProcessMotionCaptureDataThreadWorker(
            recording_parameter_model, kill_event=threading.Event()
        )
        self._process_motion_capture_data_thread_worker.start()

    def _get_calibration_toml_path(self,
                                   recording_parameter_model: ProcessingParameterModel) -> ProcessingParameterModel:
        if self._calibration_picker_widget.calibration_toml_path:
            recording_parameter_model.recording_info_model.calibration_toml_path = (
                self._calibration_picker_widget.calibration_toml_path
            )
        else:
            recording_parameter_model.recording_info_model.calibration_toml_path = (
                self._calibration_picker_widget.open_load_camera_calibration_toml_dialog()
            )
        if not recording_parameter_model.recording_info_model.calibration_toml_path:
            raise FileNotFoundError("No calibration TOML selected/found!")

        return recording_parameter_model


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    window = BatchProcessRecodingControlPanel()
    window.show()
    app.exec()
