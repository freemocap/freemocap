import logging
import time
from typing import Dict

import cv2
import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.dockarea.Dock import Dock
from pyqtgraph.dockarea.DockArea import DockArea
from pyqtgraph.Qt import QtWidgets

from src.core_processor.timestamp_manager.timestamp_manager import TimestampManager
from src.pipelines.session_pipeline.data_classes.data_3d_single_frame_payload import Data3dSingleFramePayload

logger = logging.getLogger(__name__)


class QTVisualizerAndGui:
    def __init__(self):
        # https://pyqtgraph.readthedocs.io/en/latest/config_options.html
        self.pyqtgraph_app = pg.mkQApp('freemocap! :D')
        pg.setConfigOptions(imageAxisOrder='row-major')

        self._dict_of_camera_image_item_widgets = {}
        self._dict_of_simple_timestamp_line_plots = {}
        self._dict_of_cam_timestamps = {}
        self._dict_of_timestamp_difference_line_plots = {}
        self._dict_of_cam_timestamp_differences = {}
        self._dict_of_timestamp_difference_histograms = {}
        self._number_of_cameras = None
        self._webcam_ids_list = []

        self._is_paused = False
        self._shut_it_down = False

    @property
    def shut_it_down(self):
        return self._shut_it_down

    @property
    def pause_button_pressed(self):
        return self._is_paused

    def _close_button_pressed(self):
        self.close()
        self._shut_it_down = True

    def close(self):
        self._main_window_widget.close()


    def setup_and_launch(self, webcam_ids_list):
        logger.info('setting up QT Visualizer and GUI')
        self._number_of_cameras = len(webcam_ids_list)
        self._webcam_ids_list = webcam_ids_list
        self._setup_main_window()
        self._setup_control_panel()
        self._setup_camera_views_dock()
        # self._setup_timestamp_plot()
        # self._setup_time_difference_from_cam0_line_plot()
        # self._setup_time_difference_from_cam0_histogram_plot()
        self._setup_3d_viewport()
        logger.info('launching QT Visualizer and GUI window')
        self._main_window_widget.show()

    def update_camera_view_image(self, webcam_id, image_to_display):
        if self.pause_button_pressed:
            return

        try:
            camera_image_item_widget = self._dict_of_camera_image_item_widgets[webcam_id]
        except Exception as e:
            logger.warning(f'Could not find ViewBoxWidget for camera {webcam_id}')
            raise e
        camera_image_item_widget.setImage(cv2.cvtColor(image_to_display, cv2.COLOR_BGR2RGB))

    def update_timestamp_plots(self, timestamp_manager: TimestampManager):
        if self.pause_button_pressed:
            return
        if timestamp_manager.get_timestamps_from_camera(self._camera0_id).number_of_frames <= 0:
            return

        self._update_simple_timestamp_plot(timestamp_manager)
        self._update_timestamp_difference_plot(timestamp_manager)
        self._update_timestamp_difference_histogram(timestamp_manager)

    def _update_simple_timestamp_plot(self, timestamp_manager: TimestampManager):
        for webcam_id in self._webcam_ids_list:
            plot_item = self._dict_of_simple_timestamp_line_plots[webcam_id]
            plot_item.setData(timestamp_manager.get_timestamps_from_camera(webcam_id).timestamps_unix_ns)

    def _update_timestamp_difference_plot(self, timestamp_manager: TimestampManager):
        for webcam_id in self._webcam_ids_list:
            plot_item = self._dict_of_simple_timestamp_line_plots[webcam_id]
            plot_item.setData(np.diff(timestamp_manager.get_timestamps_from_camera(webcam_id).timestamps_unix_ns))

    def _update_timestamp_difference_histogram(self, timestamp_manager: TimestampManager):
        for webcam_id in self._webcam_ids_list:
            this_cam_timestamp_diffs = np.diff(timestamp_manager.get_timestamps_from_camera(webcam_id).timestamps_unix_ns)
            num_samples = this_cam_timestamp_diffs.shape[0]
            counts, bin_edges = np.histogram(this_cam_timestamp_diffs,
                                             bins=np.linspace(0, 100, 100))
            counts = counts / num_samples
            try:
                self._dict_of_timestamp_difference_histograms[webcam_id].setData(
                    x=bin_edges,
                    y=counts)
            except Exception as e:
                logger.warning(f'Could not find timestamp difference line plot widget for camera {webcam_id}')
                raise e

    def _setup_main_window(self, window_width: int = 1000, window_height: int = 1000):
        """
        This is the main main window for the GUI.
        Its structure is based loosely on the 'Dock Widgets' example from `python -m pyqtgraph.examples`
        """
        self._main_window_widget = QtWidgets.QMainWindow()
        self._main_window_widget.resize(window_width, window_height)

        self._main_dock_area = DockArea()
        self._main_window_widget.setCentralWidget(self._main_dock_area)
        self._main_window_widget.setWindowTitle('Main Window ;D')

    def _setup_control_panel(self):
        self._control_panel_dock = Dock('Control Panel', size=(1, 1))
        control_panel_layout_widget = pg.LayoutWidget()
        self._control_panel_dock.addWidget(control_panel_layout_widget)

        label = QtWidgets.QLabel("Blah Blah Blah put words here ")
        control_panel_layout_widget.addWidget(label, row=0, col=0)

        self._pause_button = QtWidgets.QPushButton('Pause')
        self._pause_button.setEnabled(True)
        self._pause_button.clicked.connect(self._pause)
        control_panel_layout_widget.addWidget(self._pause_button, row=1, col=0)

        self._play_button = QtWidgets.QPushButton('Resume')
        self._play_button.setEnabled(False)
        self._play_button.clicked.connect(self._play)
        control_panel_layout_widget.addWidget(self._play_button, row=2, col=0)

        # self._reset_calibration_button = QtWidgets.QPushButton('Reset Calibration')
        # self._reset_calibration_button.setEnabled(False)
        # self._reset_calibration_button.clicked.connect(self._reset_calibration)
        # control_panel_layout_widget.addWidget(self._reset_calibration_button, row=3, col=0)
        #
        # self._record_button = QtWidgets.QPushButton('Record')
        # self._record_button.setEnabled(False)
        # self._record_button.clicked.connect(self._record)
        # control_panel_layout_widget.addWidget(self._record_button, row=3, col=0)

        self._close_button = QtWidgets.QPushButton('Close All')
        self._close_button.setEnabled(True)
        self._close_button.clicked.connect(self._close_button_pressed)
        control_panel_layout_widget.addWidget(self._close_button, row=4, col=0)

        self._main_dock_area.addDock(self._control_panel_dock, position='left')

    def _setup_camera_views_dock(self):
        self._camera_graphics_layout_window = pg.GraphicsLayoutWidget()
        self._camera_views_dock = Dock('Camera Views')
        self._camera_views_dock.addWidget(self._camera_graphics_layout_window)
        self._main_dock_area.addDock(self._camera_views_dock, 'right', self._control_panel_dock)

        for this_webcam_id in self._webcam_ids_list:
            self._dict_of_camera_image_item_widgets[this_webcam_id] = self._create_camera_view_widget()

    def _create_camera_view_widget(self):
        camera_view_box_widget = pg.ViewBox(invertY=True, lockAspect=True)
        camera_image_item = pg.ImageItem()
        camera_view_box_widget.addItem(camera_image_item)
        self._camera_graphics_layout_window.addItem(camera_view_box_widget)
        return camera_image_item

    def _setup_timestamp_plot(self):
        # create widget/dock for reprojection error subplot
        timestamp_plot_widget = pg.PlotWidget(title="Timestamp vs Frame#")
        timestamp_plot_widget.setLabel('left', "timestamp", units='seconds')
        timestamp_plot_widget.setLabel('bottom', "Frame#", units='Frame')
        timestamp_plot_widget.addLegend()

        for this_cam_num, this_webcam_id in enumerate(self._webcam_ids_list):
            this_timestamp_plot_line = timestamp_plot_widget.plot(np.empty(0),
                                                                  pen=(this_cam_num, self._number_of_cameras),
                                                                  name="camera " + this_webcam_id)

            self._dict_of_simple_timestamp_line_plots[this_webcam_id] = this_timestamp_plot_line
            self._dict_of_cam_timestamps[this_webcam_id] = np.ndarray(0)

        self._timestamp_plot_dock = Dock("Camera Timestamps")
        self._timestamp_plot_dock.addWidget(timestamp_plot_widget)
        self._main_dock_area.addDock(self._timestamp_plot_dock, 'bottom')

    def _setup_time_difference_from_cam0_line_plot(self):
        # create widget/dock for reprojection error subplot
        timestamp_difference_plot_widget = pg.PlotWidget(title="Timestamp difference from Camera0 on each frame")
        timestamp_difference_plot_widget.setLabel('left', "np.abs(this_camera timestamp - cam0 timestamp)",
                                                  units='milliseconds')
        timestamp_difference_plot_widget.setLabel('bottom', "Frame#", units='Frame')
        timestamp_difference_plot_widget.addLegend()

        for this_cam_num, this_webcam_id in enumerate(self._webcam_ids_list):
            this_plot_line = timestamp_difference_plot_widget.plot(np.empty(0),
                                                                   pen=(this_cam_num, self._number_of_cameras),
                                                                   name="camera " + this_webcam_id)

            self._dict_of_timestamp_difference_line_plots[this_webcam_id] = this_plot_line
            self._dict_of_cam_timestamp_differences[this_webcam_id] = np.ndarray(0)

        self._timestamp_difference_plot_dock = Dock("Camera Timestamps")
        self._timestamp_difference_plot_dock.addWidget(timestamp_difference_plot_widget)
        self._main_dock_area.addDock(self._timestamp_difference_plot_dock, 'right', self._timestamp_plot_dock)

    def _setup_time_difference_from_cam0_histogram_plot(self):
        timestamp_difference_histogram_plot_widget = pg.PlotWidget(
            title="Timestamp difference from Camera0 on each frame")
        timestamp_difference_histogram_plot_widget.setLabel('left', "Proportion")
        timestamp_difference_histogram_plot_widget.setLabel('bottom', "milliseconds")
        timestamp_difference_histogram_plot_widget.addLegend()

        for this_cam_num, this_webcam_id in enumerate(self._webcam_ids_list):
            this_histogram_plot_item = timestamp_difference_histogram_plot_widget.plot(np.empty(0),
                                                                                       np.empty(0),
                                                                                       stepMode="center",
                                                                                       fillLevel=0,
                                                                                       fillOutline=False,
                                                                                       brush=pg.mkBrush(color=(
                                                                                           this_cam_num,
                                                                                           self._number_of_cameras),
                                                                                           alpha=.5),
                                                                                       name="camera " + this_webcam_id)

            self._dict_of_timestamp_difference_histograms[this_webcam_id] = this_histogram_plot_item

        self._timestamp_diff_histgoram_dock = Dock("Camera Timestamp Difference histogram")
        self._timestamp_diff_histgoram_dock.addWidget(timestamp_difference_histogram_plot_widget)
        self._main_dock_area.addDock(self._timestamp_diff_histgoram_dock, 'right', self._timestamp_difference_plot_dock)

    def _pause(self):
        self._is_paused = True
        self._play_button.setEnabled(True)
        self._play_button.setText("GUI Paused - Main loop still active")
        self._pause_button.setEnabled(False)

    def _play(self):
        self._is_paused = False
        self._play_button.setEnabled(False)
        self._pause_button.setEnabled(True)

    def _reset_calibration(self):
        pass

    def _record(self):
        pass

    def _setup_3d_viewport(self):
        self.opengl_3d_plot_widget = gl.GLViewWidget()
        self.opengl_3d_plot_widget.opts['distance'] = 2000
        self.opengl_grid_item = gl.GLGridItem()
        self.opengl_3d_plot_widget.addItem(self.opengl_grid_item)

        # create XYZ axes
        x_axis_line_array = np.array([[0, 0, 0], [1, 0, 0]])
        y_axis_line_array = np.array([[0, 0, 0], [0, 1, 0]])
        z_axis_line_array = np.array([[0, 0, 0], [0, 0, 1]])

        self.origin_x_axis_gl_lineplot_item = pg.opengl.GLLinePlotItem(pos=x_axis_line_array,
                                                                       color=(1, 0, 0, 1),
                                                                       width=1.,
                                                                       antialias=True)
        self.origin_y_axis_gl_lineplot_item = pg.opengl.GLLinePlotItem(pos=y_axis_line_array,
                                                                       color=(0, 1, 0, 1),
                                                                       width=1.,
                                                                       antialias=True)
        self.origin_z_axis_gl_lineplot_item = pg.opengl.GLLinePlotItem(pos=z_axis_line_array,
                                                                       color=(0, 0, 1, 1),
                                                                       width=1.,
                                                                       antialias=True)
        self.opengl_3d_plot_widget.addItem(self.origin_x_axis_gl_lineplot_item)
        self.opengl_3d_plot_widget.addItem(self.origin_y_axis_gl_lineplot_item)
        self.opengl_3d_plot_widget.addItem(self.origin_z_axis_gl_lineplot_item)

        self.opengl_charuco_scatter_item = gl.GLScatterPlotItem(pos=(0, 0, 0),
                                                                color=(1, 0, 1),
                                                                size=1,
                                                                pxMode=False)

        self.opengl_3d_plot_dock = Dock("3d View Port")
        self.opengl_3d_plot_dock.addWidget(self.opengl_3d_plot_widget)
        self._main_dock_area.addDock(self.opengl_3d_plot_dock, 'bottom', self._camera_views_dock)

    def update_charuco_3d_dottos(self, charuco_frame_payload: Data3dSingleFramePayload):
        self._charuco_scatter_item.setData(
            pos=charuco_frame_payload.data3d_trackedPointNum_xyz
        )

    def initialize_charuco_dottos(self, number_of_charuco_corners: int):
        dummy_charuco_points = np.zeros((number_of_charuco_corners, 3))
        self._charuco_scatter_item = gl.GLScatterPlotItem(
            pos=dummy_charuco_points,
            color=(1, 1, 0, 1),
            size=20
        )
        self.opengl_3d_plot_widget.addItem(self._charuco_scatter_item)



if __name__ == "__main__":
    pass