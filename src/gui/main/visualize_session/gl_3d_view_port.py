import logging
from typing import Union

import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from pyqtgraph.dockarea.Dock import Dock

from src.core_processes.mediapipe_2d_skeleton_detector.mediapipe_skeleton_names_and_connections import (
    mediapipe_body_connections,
)
from src.pipelines.session_pipeline.data_classes.data_3d_single_frame_payload import (
    Data3dMultiFramePayload,
)

logger = logging.getLogger(__name__)


class Gl3dViewPort(QWidget):
    def __init__(self):
        logger.info("setting up Visualizer3d")
        super().__init__()

        self._mediapipe_connections_dict = {}
        self._base_scalar = 2e3  # 2 meters, probably
        self._mediapipe_skeleton_scatter_item = None
        self._mediapipe_body_connections = mediapipe_body_connections

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._opengl_3d_plot_widget = gl.GLViewWidget()
        self._setup_3d_view(initial_viewing_distance=self._base_scalar)
        self._layout.addWidget(self._opengl_3d_plot_widget)

    def _setup_3d_view(self, initial_viewing_distance: Union[float, int] = 2e3):
        self._opengl_3d_plot_widget.opts["distance"] = initial_viewing_distance
        self._create_grid_planes(grid_scale=initial_viewing_distance)
        self._create_rgb_origin_axes()

    def _create_rgb_origin_axes(self):
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
        self._opengl_3d_plot_widget.addItem(self.origin_x_axis_gl_lineplot_item)
        self._opengl_3d_plot_widget.addItem(self.origin_y_axis_gl_lineplot_item)
        self._opengl_3d_plot_widget.addItem(self.origin_z_axis_gl_lineplot_item)

    def _create_grid_planes(self, grid_scale: Union[int, float] = 2e3):

        # create the background grids
        grid_plane_x = gl.GLGridItem()
        grid_plane_x.setSize(grid_scale, grid_scale, grid_scale)
        grid_plane_x.setSpacing(grid_scale / 10, grid_scale / 10, grid_scale / 10)
        grid_plane_x.rotate(90, 0, 1, 0)
        grid_plane_x.translate(-grid_scale, 0, 0)
        self._opengl_3d_plot_widget.addItem(grid_plane_x)

        grid_plane_y = gl.GLGridItem()
        grid_plane_y.setSize(grid_scale, grid_scale, grid_scale)
        grid_plane_y.setSpacing(grid_scale / 10, grid_scale / 10, grid_scale / 10)
        grid_plane_y.rotate(90, 1, 0, 0)
        grid_plane_y.translate(0, -grid_scale, 0)
        self._opengl_3d_plot_widget.addItem(grid_plane_y)

        grid_plane_z = gl.GLGridItem()
        grid_plane_z.setSize(grid_scale, grid_scale, grid_scale)
        grid_plane_z.setSpacing(grid_scale / 10, grid_scale / 10, grid_scale / 10)
        grid_plane_z.translate(0, 0, -grid_scale)
        self._opengl_3d_plot_widget.addItem(grid_plane_z)

    def _initialize_mediapipe_skeleton_dottos(
        self, mediapipe_trackedPoint_xyz: np.ndarray
    ):
        self._mediapipe_skeleton_scatter_item = gl.GLScatterPlotItem(
            pos=mediapipe_trackedPoint_xyz, color=(0, 1, 1, 1), size=10, pxMode=False
        )
        self._opengl_3d_plot_widget.addItem(self._mediapipe_skeleton_scatter_item)

    def _initialize_mediapipe_skeleton_connections(
        self, mediapipe_trackedPoint_xyz: np.ndarray
    ):
        self._skeleton_connections_list = []
        for this_connection in self._mediapipe_body_connections:
            this_skel_line = gl.GLLinePlotItem(
                pos=mediapipe_trackedPoint_xyz[this_connection, :]
            )
            self._skeleton_connections_list.append(this_skel_line)
            self._opengl_3d_plot_widget.addItem(this_skel_line)

    def update_mediapipe3d_skeleton(self, mediapipe3d_trackedPoint_xyz):

        if self._mediapipe_skeleton_scatter_item is None:
            self._initialize_mediapipe_skeleton_dottos(mediapipe3d_trackedPoint_xyz)
            self._initialize_mediapipe_skeleton_connections(
                mediapipe3d_trackedPoint_xyz
            )

        # skel dottos
        self._mediapipe_skeleton_scatter_item.setData(pos=mediapipe3d_trackedPoint_xyz)

        # skel lines
        for this_skeleton_line_number, this_connection in enumerate(
            self._mediapipe_body_connections
        ):
            self._skeleton_connections_list[this_skeleton_line_number].setData(
                pos=mediapipe3d_trackedPoint_xyz[this_connection, :]
            )


if __name__ == "__main__":
    pass
