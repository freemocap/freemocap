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
from mediapipe.python.solutions import holistic as mp_holistic

from src.core_processor.timestamp_manager.timestamp_manager import TimestampManager
from src.pipelines.session_pipeline.data_classes.data_3d_single_frame_payload import (
    Data3dMultiFramePayload,
)

logger = logging.getLogger(__name__)


class QTVisualizerAndGui:
    def __init__(self):
        # https://pyqtgraph.readthedocs.io/en/latest/config_options.html
        self._skeleton_connections_list = None
        self._mediapipe_skeleton_initialized = False
        self.pyqtgraph_app = pg.mkQApp("freemocap! :D")
        pg.setConfigOptions(imageAxisOrder="row-major")

        self._dict_of_camera_image_item_widgets = {}
        self._number_of_cameras = None
        self._webcam_ids_list = []
        self._camera_set = False

        self._is_paused = False
        self._shut_it_down = False
        self._record_video_bool = False

    @property
    def shut_it_down(self):
        return self._shut_it_down

    @property
    def pause_button_pressed(self):
        return self._is_paused

    @property
    def record_button_pressed(self):
        return self._record_video_bool

    def _close_button_pressed(self):
        self.close()
        self._shut_it_down = True

    def close(self):
        self._main_window_widget.close()

    def setup_and_launch(self, webcam_ids_list):
        logger.info("setting up QT Visualizer and GUI")
        self._number_of_cameras = len(webcam_ids_list)
        self._webcam_ids_list = webcam_ids_list
        self._setup_main_window()
        self._setup_control_panel()
        self._setup_camera_views_dock()
        self._setup_3d_viewport()
        logger.info("launching QT Visualizer and GUI window")

        self._main_window_widget.show()

    def update_camera_view_image(self, webcam_id, image_to_display):
        if self.pause_button_pressed:
            return

        try:
            camera_image_item_widget = self._dict_of_camera_image_item_widgets[
                webcam_id
            ]
        except Exception as e:
            logger.warning(f"Could not find ViewBoxWidget for camera {webcam_id}")
            raise e
        camera_image_item_widget.setImage(
            cv2.cvtColor(image_to_display, cv2.COLOR_BGR2RGB)
        )

    def _setup_main_window(self, window_width: int = 1000, window_height: int = 1000):
        """
        This is the main main window for the GUI.
        Its structure is based loosely on the 'Dock Widgets' example from `python -m pyqtgraph.examples`
        """
        self._main_window_widget = QtWidgets.QMainWindow()
        self._main_window_widget.resize(window_width, window_height)

        self._main_dock_area = DockArea()
        self._main_window_widget.setCentralWidget(self._main_dock_area)
        self._main_window_widget.setWindowTitle("Main Window ;D")

    def _setup_control_panel(self):
        self._control_panel_dock = Dock("Control Panel", size=(1, 1))
        control_panel_layout_widget = pg.LayoutWidget()
        self._control_panel_dock.addWidget(control_panel_layout_widget)

        label = QtWidgets.QLabel("Blah Blah Blah put words here ")
        control_panel_layout_widget.addWidget(label, row=0, col=0)

        self._pause_button = QtWidgets.QPushButton("Pause")
        self._pause_button.setEnabled(True)
        self._pause_button.clicked.connect(self._pause)
        control_panel_layout_widget.addWidget(self._pause_button, row=1, col=0)

        self._play_button = QtWidgets.QPushButton("Resume")
        self._play_button.setEnabled(False)
        self._play_button.clicked.connect(self._play)
        control_panel_layout_widget.addWidget(self._play_button, row=2, col=0)

        # self._reset_calibration_button = QtWidgets.QPushButton('Reset Calibration')
        # self._reset_calibration_button.setEnabled(False)
        # self._reset_calibration_button.clicked.connect(self._reset_calibration)
        # control_panel_layout_widget.addWidget(self._reset_calibration_button, row=3, col=0)
        #
        self._start_record_button = QtWidgets.QPushButton("Start Recording Video")
        self._start_record_button.setEnabled(True)
        self._start_record_button.clicked.connect(self._record_button_pressed)
        control_panel_layout_widget.addWidget(self._start_record_button, row=3, col=0)

        self._close_button = QtWidgets.QPushButton("Close All")
        self._close_button.setEnabled(True)
        self._close_button.clicked.connect(self._close_button_pressed)
        control_panel_layout_widget.addWidget(self._close_button, row=4, col=0)

        self._main_dock_area.addDock(self._control_panel_dock, position="left")

    def _setup_camera_views_dock(self):
        self._camera_graphics_layout_window = pg.GraphicsLayoutWidget()
        self._camera_views_dock = Dock("Camera Views")
        self._camera_views_dock.addWidget(self._camera_graphics_layout_window)
        self._main_dock_area.addDock(
            self._camera_views_dock, "right", self._control_panel_dock
        )

        for this_webcam_id in self._webcam_ids_list:
            self._dict_of_camera_image_item_widgets[
                this_webcam_id
            ] = self._create_camera_view_widget()

    def _create_camera_view_widget(self):
        camera_view_box_widget = pg.ViewBox(invertY=True, lockAspect=True)
        camera_image_item = pg.ImageItem()
        camera_view_box_widget.addItem(camera_image_item)
        self._camera_graphics_layout_window.addItem(camera_view_box_widget)
        return camera_image_item

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

    def _record_button_pressed(self):
        if not self._record_video_bool:  # we want to start recording
            self._record_video_bool = True
            self._start_record_button.setText("Recording! Click Again to stop")
        else:
            self._record_video_bool = False
            self._start_record_button.setText(
                "Click to record more, or click Close All to stop"
            )

    def _setup_3d_viewport(self):
        self.opengl_3d_plot_widget = gl.GLViewWidget()

        # self.opengl_3d_plot_widget.opts['center'] = (0,0,0)
        self.opengl_3d_plot_widget.opts["distance"] = 2e3
        # self.opengl_3d_plot_widget.opts['azimuth'] = 0
        # self.opengl_3d_plot_widget.opts['elevation'] = 0

        self.create_grid_planes()

        # create XYZ axes
        x_axis_line_array = np.array([[0, 0, 0], [100, 0, 0]])
        y_axis_line_array = np.array([[0, 0, 0], [0, 100, 0]])
        z_axis_line_array = np.array([[0, 0, 0], [0, 0, 100]])

        self.origin_x_axis_gl_lineplot_item = pg.opengl.GLLinePlotItem(
            pos=x_axis_line_array, color=(1, 0, 0, 1), width=1.0, antialias=True
        )
        self.origin_y_axis_gl_lineplot_item = pg.opengl.GLLinePlotItem(
            pos=y_axis_line_array, color=(0, 1, 0, 1), width=1.0, antialias=True
        )
        self.origin_z_axis_gl_lineplot_item = pg.opengl.GLLinePlotItem(
            pos=z_axis_line_array, color=(0, 0, 1, 1), width=1.0, antialias=True
        )
        self.opengl_3d_plot_widget.addItem(self.origin_x_axis_gl_lineplot_item)
        self.opengl_3d_plot_widget.addItem(self.origin_y_axis_gl_lineplot_item)
        self.opengl_3d_plot_widget.addItem(self.origin_z_axis_gl_lineplot_item)

        self.opengl_charuco_scatter_item = gl.GLScatterPlotItem(
            pos=(0, 0, 0), color=(1, 0, 1, 1), size=10, pxMode=False
        )

        self.opengl_3d_plot_widget.addItem(self.opengl_charuco_scatter_item)

        self.opengl_3d_plot_dock = Dock("3d View Port")
        self.opengl_3d_plot_dock.addWidget(self.opengl_3d_plot_widget)
        self._main_dock_area.addDock(
            self.opengl_3d_plot_dock, "bottom", self._camera_views_dock
        )

    def create_grid_planes(self):
        grid_scale = 2e3
        # create the background grids
        grid_plane_x = gl.GLGridItem()
        grid_plane_x.setSize(grid_scale, grid_scale, grid_scale)
        grid_plane_x.setSpacing(grid_scale / 10, grid_scale / 10, grid_scale / 10)
        grid_plane_x.rotate(90, 0, 1, 0)
        grid_plane_x.translate(-grid_scale, 0, 0)
        self.opengl_3d_plot_widget.addItem(grid_plane_x)

        grid_plane_y = gl.GLGridItem()
        grid_plane_y.setSize(grid_scale, grid_scale, grid_scale)
        grid_plane_y.setSpacing(grid_scale / 10, grid_scale / 10, grid_scale / 10)
        grid_plane_y.rotate(90, 1, 0, 0)
        grid_plane_y.translate(0, -grid_scale, 0)
        self.opengl_3d_plot_widget.addItem(grid_plane_y)

        grid_plane_z = gl.GLGridItem()
        grid_plane_z.setSize(grid_scale, grid_scale, grid_scale)
        grid_plane_z.setSpacing(grid_scale / 10, grid_scale / 10, grid_scale / 10)
        grid_plane_z.translate(0, 0, -grid_scale)
        self.opengl_3d_plot_widget.addItem(grid_plane_z)

    def initialize_charuco_dottos(self, number_of_charuco_corners: int):
        dummy_charuco_points = np.zeros((number_of_charuco_corners, 3))
        self._charuco_scatter_item = gl.GLScatterPlotItem(
            pos=dummy_charuco_points, color=(1, 1, 0, 1), size=20
        )
        self.opengl_3d_plot_widget.addItem(self._charuco_scatter_item)

    def update_charuco_3d_dottos(self, charuco_frame_payload: Data3dMultiFramePayload):
        # if not self._camera_set:
        #     mean_xyz = np.nanmean(charuco_frame_payload.data3d_trackedPointNum_xyz,axis=0)
        #     self.opengl_3d_plot_widget.pan(mean_xyz[0], mean_xyz[1], mean_xyz[2])
        #     self._camera_set = True

        self.opengl_charuco_scatter_item.setData(
            pos=charuco_frame_payload.data3d_trackedPointNum_xyz
        )

    def get_mediapipe_connections(self):
        self.mediapipe_body_connections = [
            this_connection for this_connection in mp_holistic.POSE_CONNECTIONS
        ]
        self.mediapipe_hand_connections = [
            this_connection for this_connection in mp_holistic.HAND_CONNECTIONS
        ]
        self.mediapipe_face_connections = [
            this_connection for this_connection in mp_holistic.FACEMESH_TESSELATION
        ]

    def initialize_skel_dottos(self, mediapipe_trackedPoint_xyz: np.ndarray):
        self.skeleton_scatter_item = gl.GLScatterPlotItem(
            pos=mediapipe_trackedPoint_xyz, color=(0, 1, 1, 1), size=10, pxMode=False
        )
        self.opengl_3d_plot_widget.addItem(self.skeleton_scatter_item)

    def initialize_skel_lines(self, mediapipe_trackedPoint_xyz: np.ndarray):
        self._skeleton_connections_list = []
        for this_connection in self.mediapipe_body_connections:
            this_skel_line = gl.GLLinePlotItem(
                pos=mediapipe_trackedPoint_xyz[this_connection, :]
            )
            self._skeleton_connections_list.append(this_skel_line)
            self.opengl_3d_plot_widget.addItem(this_skel_line)

    def update_mediapipe3d_skeleton(self, mediapipe3d_multi_frame_payload):
        mediapipe3d_trackedPoint_xyz = (
            mediapipe3d_multi_frame_payload.data3d_trackedPointNum_xyz
        )
        if not self._mediapipe_skeleton_initialized:
            self.get_mediapipe_connections()
            self.initialize_skel_dottos(mediapipe3d_trackedPoint_xyz)
            self.initialize_skel_lines(mediapipe3d_trackedPoint_xyz)
            self._mediapipe_skeleton_initialized = True

        # skel dottos
        self.skeleton_scatter_item.setData(pos=mediapipe3d_trackedPoint_xyz)

        # skel lines
        for this_skeleton_line_number, this_connection in enumerate(
            self.mediapipe_body_connections
        ):
            self._skeleton_connections_list[this_skeleton_line_number].setData(
                pos=mediapipe3d_trackedPoint_xyz[this_connection, :]
            )


if __name__ == "__main__":
    pass
