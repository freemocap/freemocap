# adapted from - https://gist.github.com/markjay4k/da2f55e28514be7160a7c5fbf95bd243
from pathlib import Path

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph.opengl as gl
import pyqtgraph as pg
import numpy as np
import sys
from mediapipe.python.solutions import holistic as mp_holistic


class QT_GL_LaserSkeleton():
    def __init__(self, session_path: Path):
        self.mediapipe_fr_mar_xyz = None
        self.session_path = Path(session_path)
        self.traces = dict()
        self.start_frame_number = 1000
        self.end_frame_number = 2000
        self.current_frame_number = self.start_frame_number

        self.load_mediapipe_data()
        self.load_pupil_data()

        self.create_app_window()
        self.create_grid_planes()
        self.get_mediapipe_connections()
        self.initialize_skel_dottos()
        self.initialize_skel_lines()
        self.initialize_gaze_laser()

    def load_mediapipe_data(self):
        mediapipe_data_path = self.session_path / 'DataArrays' / 'mediaPipeSkel_3d_smoothed.npy'
        mediapipe_all_fr_mar_xyz = np.load(str(mediapipe_data_path))
        self.mean_position_xyz = np.nanmedian(np.nanmedian(mediapipe_all_fr_mar_xyz, axis=0), axis=0)
        mediapipe_all_fr_mar_xyz[:, :, 0] -= self.mean_position_xyz[0]
        mediapipe_all_fr_mar_xyz[:, :, 1] -= self.mean_position_xyz[1]
        mediapipe_all_fr_mar_xyz[:, :, 2] -= self.mean_position_xyz[2]

        # remove first frame due to annoying 'off-by-one' error in the timestamp logger
        mediapipe_all_fr_mar_xyz = np.delete(mediapipe_all_fr_mar_xyz, 0, axis=0)

        self.mediapipe_fr_mar_xyz = mediapipe_all_fr_mar_xyz[:, :75, :]

    def load_pupil_data(self):
        pupil_data_path = self.session_path / 'pupil_000' / 'exports' / '000' / 'right_eye_gaze_xyz.npy'
        right_gaze_xyz = np.load(str(pupil_data_path))

        right_eye_d = 5
        self.right_eye_xyz = np.squeeze(self.mediapipe_fr_mar_xyz[:, right_eye_d, :])

        right_gaze_xyz[:, 0] += self.right_eye_xyz[:, 0]
        right_gaze_xyz[:, 1] += self.right_eye_xyz[:, 1]
        right_gaze_xyz[:, 2] += self.right_eye_xyz[:, 2]

        self.right_gaze_xyz = right_gaze_xyz

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

        self.skeleton_scatter_item.setData(
            pos=self.mediapipe_fr_mar_xyz[self.current_frame_number, :, :]
        )
        self.update_skeleton_lines()
        this_gaze_laser = np.vstack(
            (self.right_eye_xyz[self.current_frame_number, :], self.right_gaze_xyz[self.current_frame_number, :]))
        self.right_gaze_line_item.setData(pos=this_gaze_laser)

    def update_skeleton_lines(self):
        for this_skeleton_line_number, this_connection in enumerate(self.mediapipe_body_connections):
            self.skeleton_connections_list[this_skeleton_line_number].setData(
                pos=self.mediapipe_fr_mar_xyz[self.current_frame_number, this_connection, :]
            )

    def update_frame_number(self):
        self.current_frame_number += 1
        if self.current_frame_number >= self.end_frame_number:
            self.current_frame_number = self.start_frame_number
        if self.current_frame_number % 10 == 0:
            print(f'frame number: {self.current_frame_number}')

    def start(self):
        print('starting')
        pg.exec()

    def start_animation(self):
        print('starting animation')
        timer = QtCore.QTimer()
        timer.timeout.connect(self.update)
        timer.start(33)
        self.start()


if __name__ == '__main__':
    data_path = Path('C:/Users/jonma/Dropbox/FreeMoCapProject/FreeMocap_Data/')
    session_path = data_path / 'sesh_2022-02-15_11_54_28_pupil_maybe'

    qt_gl_laser_skeleton = QT_GL_LaserSkeleton(session_path)
    qt_gl_laser_skeleton.start_animation()
