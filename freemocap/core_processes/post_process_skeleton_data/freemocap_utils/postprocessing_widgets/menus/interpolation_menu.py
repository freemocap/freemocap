
import numpy as np

from PyQt6.QtWidgets import QWidget,QVBoxLayout, QPushButton,QGroupBox

from freemocap_utils.postprocessing_widgets.task_worker_thread import TaskWorkerThread
from freemocap_utils.postprocessing_widgets.parameter_tree_builder import  create_interpolation_parameter_tree, create_interpolation_page_settings_dict
from freemocap_utils.postprocessing_widgets.visualization_widgets.timeseries_view_widget import TimeSeriesPlotterWidget
from freemocap_utils.postprocessing_widgets.visualization_widgets.marker_selector_widget import MarkerSelectorWidget
from freemocap_utils.postprocessing_widgets.stylesheet import groupbox_stylesheet

from freemocap_utils.constants import (
    TASK_INTERPOLATION,
)


class InterpolationMenu(QWidget):
    def __init__(self, freemocap_raw_data:np.ndarray):
        super().__init__()
        layout = QVBoxLayout()

        
        self.setStyleSheet(groupbox_stylesheet)

        self.freemocap_raw_data = freemocap_raw_data
        self.processed_freemocap_data = None

        self.time_series_groupbox = self.create_time_series_groupbox()
        self.interpolation_param_tree_groupbox = self.create_interpolation_groupbox()

        layout.addWidget(self.time_series_groupbox)
        layout.addWidget(self.interpolation_param_tree_groupbox)
    
        self.run_interpolation_button = QPushButton('Run Interpolation')
        self.run_interpolation_button.clicked.connect(self.run_interpolation_task)
        layout.addWidget(self.run_interpolation_button)

        self.update_timeseries_plot()

        self.setLayout(layout)
        self.connect_signals_to_slots()

    def create_time_series_groupbox(self):
        groupbox = QGroupBox("View time series for a selected marker")
        time_series_layout = QVBoxLayout()
        self.marker_selector_widget = MarkerSelectorWidget()
        time_series_layout.addWidget(self.marker_selector_widget)
        self.time_series_plotter_widget = TimeSeriesPlotterWidget()
        time_series_layout.addWidget(self.time_series_plotter_widget)
        groupbox.setLayout(time_series_layout)
        return groupbox

    def create_interpolation_groupbox(self):
        groupbox = QGroupBox("Interpolation Parameters")
        interpolation_params_layout = QVBoxLayout()
        self.interpolation_param_tree = create_interpolation_parameter_tree()
        interpolation_params_layout.addWidget(self.interpolation_param_tree)
        groupbox.setLayout(interpolation_params_layout)
        return groupbox

    def update_timeseries_plot(self, reset_axes = True):
        self.time_series_plotter_widget.update_plot(marker_to_plot=self.marker_selector_widget.current_marker, original_freemocap_data=self.freemocap_raw_data , processed_freemocap_data=self.processed_freemocap_data,reset_axes = reset_axes)

    def connect_signals_to_slots(self):
        self.marker_selector_widget.marker_to_plot_updated_signal.connect(lambda: self.update_timeseries_plot(reset_axes=True))

    def run_interpolation_task(self):
        self.settings_dict = create_interpolation_page_settings_dict()
        self.worker_thread = TaskWorkerThread(
            raw_skeleton_data=self.freemocap_raw_data,
            task_list= [TASK_INTERPOLATION],
            settings=self.settings_dict,
            all_tasks_finished_callback=self.handle_interpolation_result)        
        self.worker_thread.start()   

    def handle_interpolation_result(self, task_results: dict):
        self.processed_freemocap_data = task_results[TASK_INTERPOLATION]['result']
        self.update_timeseries_plot(reset_axes=False)