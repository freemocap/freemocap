# adapted from - https://gist.github.com/markjay4k/da2f55e28514be7160a7c5fbf95bd243
import logging

import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from mediapipe.python.solutions import holistic as mp_holistic
from old_src.gui.refactored_gui.state.app_state import APP_STATE
from PyQt6.QtWidgets import QDialog, QVBoxLayout
from pyqtgraph.Qt import QtCore

logger = logging.getLogger(__name__)


class VisualizeSkeleton(QDialog):
    def __init__(
        self,
        mediapipe_skel_fr_mar_xyz: np.ndarray,
        start_frame: int = None,
        end_frame: int = None,
        move_data_to_origin: bool = True,
    ):
        super().__init__()

        self.mediapipe_fr_mar_xyz = mediapipe_skel_fr_mar_xyz

        if move_data_to_origin:
            self.move_data_to_origin()

        if start_frame is None:
            self.start_frame_number = 0
        else:
            self.start_frame_number = start_frame
        if end_frame is None:
            self.end_frame_number = self.mediapipe_fr_mar_xyz.shape[0]
        else:
            self.end_frame_number = end_frame

        self.current_frame_number = self.start_frame_number

        self.gl_view_widget = self.initialize_display_window()

        self.setWindowTitle(f"FreeMoCap Session: {APP_STATE.session_id}")

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.gl_view_widget)

        self.setLayout(self.layout)

    def initialize_display_window(self):
        self.create_app_window()
        self.create_grid_planes()
        self.get_mediapipe_connections()
        self.initialize_skel_dottos()
        self.initialize_skel_lines()
        return self.gl_view_widget

    def create_app_window(self):
        self.gl_view_widget = gl.GLViewWidget()
        self.gl_view_widget.opts["distance"] = 2000
        # self.gl_view_widget.setWindowTitle('FreeMoCap Skeleton')
        self.gl_view_widget.setGeometry(0, 110, 1920, 1080)
        # self.gl_view_widget.show()

    def create_grid_planes(self):
        grid_scale = 2e3
        # create the background grids
        grid_plane_x = gl.GLGridItem()
        grid_plane_x.setSize(grid_scale, grid_scale, grid_scale)
        grid_plane_x.setSpacing(grid_scale / 10, grid_scale / 10, grid_scale / 10)
        grid_plane_x.rotate(90, 0, 1, 0)
        grid_plane_x.translate(-grid_scale, 0, 0)
        self.gl_view_widget.addItem(grid_plane_x)

        grid_plane_y = gl.GLGridItem()
        grid_plane_y.setSize(grid_scale, grid_scale, grid_scale)
        grid_plane_y.setSpacing(grid_scale / 10, grid_scale / 10, grid_scale / 10)
        grid_plane_y.rotate(90, 1, 0, 0)
        grid_plane_y.translate(0, -grid_scale, 0)
        self.gl_view_widget.addItem(grid_plane_y)

        grid_plane_z = gl.GLGridItem()
        grid_plane_z.setSize(grid_scale, grid_scale, grid_scale)
        grid_plane_z.setSpacing(grid_scale / 10, grid_scale / 10, grid_scale / 10)
        grid_plane_z.translate(0, 0, -grid_scale)
        self.gl_view_widget.addItem(grid_plane_z)

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

    def initialize_skel_dottos(self):
        self.skeleton_scatter_item = gl.GLScatterPlotItem(
            pos=self.mediapipe_fr_mar_xyz[self.current_frame_number, :, :],
            color=(0, 1, 1, 1),
            size=10,
            pxMode=False,
        )
        self.gl_view_widget.addItem(self.skeleton_scatter_item)

    def initialize_skel_lines(self):
        self.skeleton_connections_list = []
        for this_connection in self.mediapipe_body_connections:
            this_skel_line = gl.GLLinePlotItem(
                pos=self.mediapipe_fr_mar_xyz[
                    self.current_frame_number, this_connection, :
                ]
            )
            self.skeleton_connections_list.append(this_skel_line)
            self.gl_view_widget.addItem(this_skel_line)

    def update(self):
        self.update_frame_number()
        if self.current_frame_number % 10 == 0:
            print(f"frame number: {self.current_frame_number}")

        self.update_skeleton()

    def update_skeleton(self):
        # skel dottos
        self.skeleton_scatter_item.setData(
            pos=self.mediapipe_fr_mar_xyz[self.current_frame_number, :, :]
        )

        # skel lines
        for this_skeleton_line_number, this_connection in enumerate(
            self.mediapipe_body_connections
        ):
            self.skeleton_connections_list[this_skeleton_line_number].setData(
                pos=self.mediapipe_fr_mar_xyz[
                    self.current_frame_number, this_connection, :
                ]
            )

    def update_frame_number(self):
        self.current_frame_number += 1
        if self.current_frame_number >= self.end_frame_number:
            self.current_frame_number = self.start_frame_number

    def start(self):
        print("starting animation")
        pg.exec()

    def start_animation(self):
        print("initializing display window")
        self.initialize_display_window()
        timer = QtCore.QTimer()
        timer.timeout.connect(self.update)
        timer.start(33)
        # self.start()

    def move_data_to_origin(self):
        mean_position_xyz = np.nanmedian(
            np.nanmedian(self.mediapipe_fr_mar_xyz, axis=0), axis=0
        )

        self.mediapipe_fr_mar_xyz[:, :, 0] -= mean_position_xyz[0]
        self.mediapipe_fr_mar_xyz[:, :, 1] -= mean_position_xyz[1]
        self.mediapipe_fr_mar_xyz[:, :, 2] -= mean_position_xyz[2]
