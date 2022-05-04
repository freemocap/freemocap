# adapted from - https://gist.github.com/markjay4k/da2f55e28514be7160a7c5fbf95bd243
import logging
from pathlib import Path

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph.opengl as gl
import pyqtgraph as pg
import numpy as np
import sys
from mediapipe.python.solutions import holistic as mp_holistic

from jon_scratch.pupil_calibration_pipeline.data_classes.freemocap_session_data_class import FreemocapSessionDataClass
from jon_scratch.pupil_calibration_pipeline.session_data_loader import SessionDataLoader

logger = logging.getLogger(__name__)


class QtGlLaserSkeletonVisualizer():
    session_path: Path = None

    def __init__(self, session_data: FreemocapSessionDataClass = None, mediapipe_skel_fr_mar_xyz: np.ndarray = None):
        if session_data is not None:
            self.mediapipe_fr_mar_xyz = session_data.mediapipe_skel_fr_mar_dim
        elif mediapipe_skel_fr_mar_xyz is not None:
            self.mediapipe_fr_mar_xyz = mediapipe_skel_fr_mar_xyz
        else:
            raise ValueError("Must provide either session data or mediapipe skeleton data")

        self.traces = dict()
        self.start_frame_number = 1000
        self.end_frame_number = 2000
        self.current_frame_number = self.start_frame_number

    def initialize_display_window(self):
        self.create_app_window()
        self.create_grid_planes()
        self.get_mediapipe_connections()
        self.initialize_skel_dottos()
        self.initialize_skel_lines()
        # self.initialize_gaze_laser()

    def create_app_window(self):
        self.app = pg.mkQApp("Laser Skeleton")
        self.gl_view_widget = gl.GLViewWidget()
        self.gl_view_widget.opts['distance'] = 2000
        self.gl_view_widget.setWindowTitle('FreeMoCap - Laser Skeleton')
        self.gl_view_widget.setGeometry(0, 110, 1920, 1080)
        self.gl_view_widget.show()

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
        self.mediapipe_body_connections = [this_connection for this_connection in mp_holistic.POSE_CONNECTIONS]
        self.mediapipe_hand_connections = [this_connection for this_connection in mp_holistic.HAND_CONNECTIONS]
        self.mediapipe_face_connections = [this_connection for this_connection in mp_holistic.FACEMESH_TESSELATION]

    def initialize_skel_dottos(self):
        self.skeleton_scatter_item = gl.GLScatterPlotItem(
            pos=self.mediapipe_fr_mar_xyz[self.current_frame_number, :, :], color=(0, 1, 1, 1), size=10,
            pxMode=False
        )
        self.gl_view_widget.addItem(self.skeleton_scatter_item)

    def initialize_skel_lines(self):
        self.skeleton_connections_list = []
        for this_connection in self.mediapipe_body_connections:
            this_skel_line = gl.GLLinePlotItem(
                pos=self.mediapipe_fr_mar_xyz[self.current_frame_number, this_connection, :])
            self.skeleton_connections_list.append(this_skel_line)
            self.gl_view_widget.addItem(this_skel_line)

    def initialize_gaze_laser(self):

        this_gaze_laser = np.vstack(
            (self.right_eye_xyz[self.current_frame_number, :], self.right_gaze_xyz[self.current_frame_number, :]))
        self.right_gaze_line_item = gl.GLLinePlotItem(pos=this_gaze_laser,
                                                      color=(1, 0, 0, 1), )
        self.gl_view_widget.addItem(self.right_gaze_line_item)

    def update(self):
        self.update_frame_number()
        if self.current_frame_number % 10 == 0:
            print(f'frame number: {self.current_frame_number}')

        self.skeleton_scatter_item.setData(
            pos=self.mediapipe_fr_mar_xyz[self.current_frame_number, :, :]
        )
        self.update_skeleton_lines()
        # this_gaze_laser = np.vstack(
        #     (self.right_eye_xyz[self.current_frame_number, :], self.right_gaze_xyz[self.current_frame_number, :]))
        # self.right_gaze_line_item.setData(pos=this_gaze_laser)

    def update_skeleton_lines(self):
        for this_skeleton_line_number, this_connection in enumerate(self.mediapipe_body_connections):
            self.skeleton_connections_list[this_skeleton_line_number].setData(
                pos=self.mediapipe_fr_mar_xyz[self.current_frame_number, this_connection, :]
            )

    def update_frame_number(self):
        self.current_frame_number += 1
        if self.current_frame_number >= self.end_frame_number:
            self.current_frame_number = self.start_frame_number


    def start(self):
        print('starting animation')
        pg.exec()

    def start_animation(self):
        print('initializing display window')
        self.initialize_display_window()
        timer = QtCore.QTimer()
        timer.timeout.connect(self.update)
        timer.start(33)
        self.start()


if __name__ == '__main__':
    # session_id = 'sesh_2022-02-15_11_54_28_pupil_maybe'
    session_id = 'sesh_2022-05-03_13_43_00_JSM_treadmill_day2_t0'
    data_path = Path('C:/Users/jonma/Dropbox/FreeMoCapProject/FreeMocap_Data/')
    session_path = data_path / session_id

    session_data_loader = SessionDataLoader(session_path)
    mediapipe_skel_fr_mar_xyz_in = session_data_loader.load_mediapipe_data(move_to_origin=True)
    print(f'mediapipe_skel_fr_mar_xyz.shape: {mediapipe_skel_fr_mar_xyz_in.shape}')
    qt_gl_laser_skeleton = QtGlLaserSkeletonVisualizer(mediapipe_skel_fr_mar_xyz = mediapipe_skel_fr_mar_xyz_in,)
    qt_gl_laser_skeleton.start_animation()
