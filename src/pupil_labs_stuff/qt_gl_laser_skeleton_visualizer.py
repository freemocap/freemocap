# adapted from - https://gist.github.com/markjay4k/da2f55e28514be7160a7c5fbf95bd243
import logging
from pathlib import Path
from typing import Union

import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from jon_scratch.pupil_calibration_pipeline.data_classes.freemocap_session_data_class import (
    FreemocapSessionDataClass,
)
from jon_scratch.pupil_calibration_pipeline.data_classes.rotation_data_class import (
    RotationDataClass,
)
from jon_scratch.pupil_calibration_pipeline.session_data_loader import SessionDataLoader
from mediapipe.python.solutions import holistic as mp_holistic
from pyqtgraph.Qt import QtCore

logger = logging.getLogger(__name__)


class QtGlLaserSkeletonVisualizer:
    session_path: Path = None

    def __init__(
        self,
        session_data: FreemocapSessionDataClass = None,
        mediapipe_skel_fr_mar_xyz: np.ndarray = None,
        start_frame: int = None,
        end_frame: int = None,
        move_data_to_origin: bool = True,
    ):

        if session_data is not None:
            self.session_data = session_data
            self.mediapipe_fr_mar_xyz = session_data.mediapipe_skel_fr_mar_xyz
        elif mediapipe_skel_fr_mar_xyz is not None:
            self.mediapipe_fr_mar_xyz = mediapipe_skel_fr_mar_xyz
        else:
            raise ValueError(
                "Must provide either session data or mediapipe skeleton data"
            )

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

    def initialize_display_window(self):
        self.create_app_window()
        self.create_grid_planes()
        self.get_mediapipe_connections()
        self.initialize_skel_dottos()
        self.initialize_skel_lines()
        self.initialize_head_axes()
        self.initialize_eye_socket_axes()
        if self.session_data.right_gaze_vector_endpoint_fr_xyz is not None:
            self.initialize_gaze_lasers()
            self.initialize_gaze_laser_tails(tail_length=30)

    def create_app_window(self):
        self.app = pg.mkQApp("Laser Skeleton")
        self.gl_view_widget = gl.GLViewWidget()
        self.gl_view_widget.opts["distance"] = 2000
        self.gl_view_widget.setWindowTitle("FreeMoCap - Laser Skeleton")
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

    def initialize_gaze_lasers(self):
        # right eye
        this_frame_right_gaze_origin = (
            self.session_data.right_eye_socket_rotation_data.local_origin_fr_xyz[0, :]
        )
        this_frame_right_gaze_endpoint = (
            self.session_data.right_gaze_vector_endpoint_fr_xyz[0, :]
        )
        this_frame_right_gaze_laser = np.array(
            [this_frame_right_gaze_origin, this_frame_right_gaze_endpoint]
        )

        self.right_gaze_vector_line_item = gl.GLLinePlotItem(
            pos=this_frame_right_gaze_laser, color=(1, 0, 1, 1), width=3
        )

        self.gl_view_widget.addItem(self.right_gaze_vector_line_item)

        # left eye
        this_frame_left_gaze_origin = (
            self.session_data.left_eye_socket_rotation_data.local_origin_fr_xyz[0, :]
        )
        this_frame_left_gaze_endpoint = (
            self.session_data.left_gaze_vector_endpoint_fr_xyz[0, :]
        )
        this_frame_left_gaze_laser = np.array(
            [this_frame_left_gaze_origin, this_frame_left_gaze_endpoint]
        )

        self.left_gaze_vector_line_item = gl.GLLinePlotItem(
            pos=this_frame_left_gaze_laser, color=(0, 1, 1, 1), width=3
        )

        self.gl_view_widget.addItem(self.left_gaze_vector_line_item)

    def initialize_gaze_laser_tails(self, tail_length):
        self.tail_length = tail_length
        dummy_tail = np.empty((self.tail_length, 3))
        dummy_tail[:] = np.nan
        self.right_gaze_laser_tail_line_item = gl.GLLinePlotItem(
            pos=dummy_tail, color=(1, 0, 1, 0.5), width=2
        )
        self.left_gaze_laser_tail_line_item = gl.GLLinePlotItem(
            pos=dummy_tail, color=(0, 1, 1, 0.5), width=2
        )

        self.gl_view_widget.addItem(self.right_gaze_laser_tail_line_item)
        self.gl_view_widget.addItem(self.left_gaze_laser_tail_line_item)

    def initialize_eye_socket_axes(self):
        self.eye_axes_scale = 1e2 / 2

        # right eye
        self.right_eye_socket_axes_x_vector_line_item = (
            self.create_axis_vector_line_item(
                0,
                self.session_data.right_eye_socket_rotation_data,
                dimension="x",
                scale=self.eye_axes_scale,
                color=(1, 0, 0, 1),
                width=3,
            )
        )
        self.right_eye_socket_axes_y_vector_line_item = (
            self.create_axis_vector_line_item(
                0,
                self.session_data.right_eye_socket_rotation_data,
                dimension="y",
                scale=self.eye_axes_scale,
                color=(0, 1, 0, 1),
                width=3,
            )
        )
        self.right_eye_socket_axes_z_vector_line_item = (
            self.create_axis_vector_line_item(
                0,
                self.session_data.right_eye_socket_rotation_data,
                dimension="z",
                scale=self.eye_axes_scale,
                color=(0, 0, 1, 1),
                width=3,
            )
        )

        self.gl_view_widget.addItem(self.right_eye_socket_axes_x_vector_line_item)
        self.gl_view_widget.addItem(self.right_eye_socket_axes_y_vector_line_item)
        self.gl_view_widget.addItem(self.right_eye_socket_axes_z_vector_line_item)

        # left eye
        self.left_eye_socket_axes_x_vector_line_item = (
            self.create_axis_vector_line_item(
                0,
                self.session_data.left_eye_socket_rotation_data,
                dimension="x",
                scale=self.eye_axes_scale,
                color=(1, 0, 0, 1),
                width=3,
            )
        )
        self.left_eye_socket_axes_y_vector_line_item = (
            self.create_axis_vector_line_item(
                0,
                self.session_data.left_eye_socket_rotation_data,
                dimension="y",
                scale=self.eye_axes_scale,
                color=(0, 1, 0, 1),
                width=3,
            )
        )
        self.left_eye_socket_axes_z_vector_line_item = (
            self.create_axis_vector_line_item(
                0,
                self.session_data.left_eye_socket_rotation_data,
                dimension="z",
                scale=self.eye_axes_scale,
                color=(0, 0, 1, 1),
                width=3,
            )
        )

        self.gl_view_widget.addItem(self.left_eye_socket_axes_x_vector_line_item)
        self.gl_view_widget.addItem(self.left_eye_socket_axes_y_vector_line_item)
        self.gl_view_widget.addItem(self.left_eye_socket_axes_z_vector_line_item)

    def initialize_head_axes(self):
        self.head_axes_scale = 1e2

        first_frame_head_center_xyz = (
            self.session_data.head_rotation_data.local_origin_fr_xyz[0, :]
        )

        self.head_axes_x_vector_line_item = self.create_axis_vector_line_item(
            0,
            self.session_data.head_rotation_data,
            dimension="x",
            scale=self.head_axes_scale,
            color=(1, 0, 0, 1),
            width=3,
        )
        self.head_axes_y_vector_line_item = self.create_axis_vector_line_item(
            0,
            self.session_data.head_rotation_data,
            dimension="y",
            scale=self.head_axes_scale,
            color=(0, 1, 0, 1),
            width=3,
        )
        self.head_axes_z_vector_line_item = self.create_axis_vector_line_item(
            0,
            self.session_data.head_rotation_data,
            dimension="z",
            scale=self.head_axes_scale,
            color=(0, 0, 1, 1),
            width=3,
        )

        self.gl_view_widget.addItem(self.head_axes_x_vector_line_item)
        self.gl_view_widget.addItem(self.head_axes_y_vector_line_item)
        self.gl_view_widget.addItem(self.head_axes_z_vector_line_item)

    def create_axis_vector_line_item(
        self,
        frame_number: int,
        rotation_data: RotationDataClass,
        dimension: Union[str, int] = None,
        scale: Union[int, float] = 1,
        color=(1, 1, 1, 1),
        width=3,
    ) -> np.ndarray:

        this_frame_axis_vector_xyz = self.unit_vector_from_rotation_matrix(
            frame_number, rotation_data, dimension=dimension, scale=scale
        )
        this_frame_axis_vector_line_item = gl.GLLinePlotItem(
            pos=this_frame_axis_vector_xyz, color=color, width=width
        )
        self.gl_view_widget.addItem(this_frame_axis_vector_line_item)
        return this_frame_axis_vector_line_item

    def unit_vector_from_rotation_matrix(
        self,
        frame_number: int,
        rotation_data: RotationDataClass,
        dimension: Union[str, int] = None,
        scale: Union[int, float] = 1,
    ) -> np.ndarray:

        try:
            if dimension == "x":
                dimension = 0
            elif dimension == "y":
                dimension = 1
            elif dimension == "z":
                dimension = 2

            if dimension > rotation_data.rotation_matricies[0].shape[1]:
                raise ValueError(
                    "dimension must be `x`, `y`, `z`, or an integer less than the number of dimensions in the rotation matrix"
                )
        except:
            raise ValueError("something weird about the `dimension` argument")

        this_rot_mat = rotation_data.rotation_matricies[frame_number]
        this_axis_vector_endpoint_xyz = rotation_data.local_origin_fr_xyz[
            frame_number, :
        ] + (this_rot_mat[dimension, :] * scale)
        this_axis_vector_origin_xyz = rotation_data.local_origin_fr_xyz[frame_number, :]

        this_axis_vector_line_xyz = np.array(
            [this_axis_vector_origin_xyz, this_axis_vector_endpoint_xyz]
        )

        return this_axis_vector_line_xyz

    def update(self):
        self.update_frame_number()
        if self.current_frame_number % 10 == 0:
            print(f"frame number: {self.current_frame_number}")

        self.skeleton_scatter_item.setData(
            pos=self.mediapipe_fr_mar_xyz[self.current_frame_number, :, :]
        )
        self.update_skeleton_lines()
        self.update_head_axis_lines()
        self.update_eye_axis_lines()
        if self.session_data.right_gaze_vector_endpoint_fr_xyz is not None:
            self.update_gaze_lasers()
            self.update_gaze_laser_tails()

    def update_skeleton_lines(self):
        for this_skeleton_line_number, this_connection in enumerate(
            self.mediapipe_body_connections
        ):
            self.skeleton_connections_list[this_skeleton_line_number].setData(
                pos=self.mediapipe_fr_mar_xyz[
                    self.current_frame_number, this_connection, :
                ]
            )

    def update_head_axis_lines(self):
        # X
        this_frame_head_axis_x_vector_xyz = self.unit_vector_from_rotation_matrix(
            self.current_frame_number,
            self.session_data.head_rotation_data,
            dimension="x",
            scale=self.head_axes_scale,
        )
        self.head_axes_x_vector_line_item.setData(pos=this_frame_head_axis_x_vector_xyz)

        # Y
        this_frame_head_axis_y_vector_xyz = self.unit_vector_from_rotation_matrix(
            self.current_frame_number,
            self.session_data.head_rotation_data,
            dimension="y",
            scale=self.head_axes_scale,
        )
        self.head_axes_y_vector_line_item.setData(pos=this_frame_head_axis_y_vector_xyz)

        # Z
        this_frame_head_axis_z_vector_xyz = self.unit_vector_from_rotation_matrix(
            self.current_frame_number,
            self.session_data.head_rotation_data,
            dimension="z",
            scale=self.head_axes_scale,
        )
        self.head_axes_z_vector_line_item.setData(pos=this_frame_head_axis_z_vector_xyz)

    def update_eye_axis_lines(self):
        # right right eye
        # X
        this_frame_right_eye_socket_axis_x_vector_xyz = (
            self.unit_vector_from_rotation_matrix(
                self.current_frame_number,
                self.session_data.right_eye_socket_rotation_data,
                dimension="x",
                scale=self.eye_axes_scale,
            )
        )
        self.right_eye_socket_axes_x_vector_line_item.setData(
            pos=this_frame_right_eye_socket_axis_x_vector_xyz
        )

        # Y
        this_frame_right_eye_socket_axis_y_vector_xyz = (
            self.unit_vector_from_rotation_matrix(
                self.current_frame_number,
                self.session_data.right_eye_socket_rotation_data,
                dimension="y",
                scale=self.eye_axes_scale,
            )
        )
        self.right_eye_socket_axes_y_vector_line_item.setData(
            pos=this_frame_right_eye_socket_axis_y_vector_xyz
        )

        # Z
        this_frame_right_eye_socket_axis_z_vector_xyz = (
            self.unit_vector_from_rotation_matrix(
                self.current_frame_number,
                self.session_data.right_eye_socket_rotation_data,
                dimension="z",
                scale=self.eye_axes_scale,
            )
        )
        self.right_eye_socket_axes_z_vector_line_item.setData(
            pos=this_frame_right_eye_socket_axis_z_vector_xyz
        )

        # left eye
        # X
        this_frame_left_eye_socket_axis_x_vector_xyz = (
            self.unit_vector_from_rotation_matrix(
                self.current_frame_number,
                self.session_data.left_eye_socket_rotation_data,
                dimension="x",
                scale=self.eye_axes_scale,
            )
        )
        self.left_eye_socket_axes_x_vector_line_item.setData(
            pos=this_frame_left_eye_socket_axis_x_vector_xyz
        )

        # Y
        this_frame_left_eye_socket_axis_y_vector_xyz = (
            self.unit_vector_from_rotation_matrix(
                self.current_frame_number,
                self.session_data.left_eye_socket_rotation_data,
                dimension="y",
                scale=self.eye_axes_scale,
            )
        )
        self.left_eye_socket_axes_y_vector_line_item.setData(
            pos=this_frame_left_eye_socket_axis_y_vector_xyz
        )

        # Z
        this_frame_left_eye_socket_axis_z_vector_xyz = (
            self.unit_vector_from_rotation_matrix(
                self.current_frame_number,
                self.session_data.left_eye_socket_rotation_data,
                dimension="z",
                scale=self.eye_axes_scale,
            )
        )
        self.left_eye_socket_axes_z_vector_line_item.setData(
            pos=this_frame_left_eye_socket_axis_z_vector_xyz
        )

    def update_gaze_lasers(self):
        # right eye
        this_right_gaze_laser_line = np.array(
            [
                self.session_data.right_eye_socket_rotation_data.local_origin_fr_xyz[
                    self.current_frame_number, :
                ],
                self.session_data.right_gaze_vector_endpoint_fr_xyz[
                    self.current_frame_number, :
                ],
            ]
        )
        self.right_gaze_vector_line_item.setData(pos=this_right_gaze_laser_line)

        # left eye
        this_left_gaze_laser_line = np.array(
            [
                self.session_data.left_eye_socket_rotation_data.local_origin_fr_xyz[
                    self.current_frame_number, :
                ],
                self.session_data.left_gaze_vector_endpoint_fr_xyz[
                    self.current_frame_number, :
                ],
            ]
        )

        self.left_gaze_vector_line_item.setData(pos=this_left_gaze_laser_line)

    def update_gaze_laser_tails(self):
        if self.current_frame_number < self.tail_length:
            return

        # right eye
        this_right_gaze_laser_tail = (
            self.session_data.right_gaze_vector_endpoint_fr_xyz[
                self.current_frame_number
                - self.tail_length : self.current_frame_number,
                :,
            ]
        )
        self.right_gaze_laser_tail_line_item.setData(pos=this_right_gaze_laser_tail)

        # left eye
        this_left_gaze_laser_tail = self.session_data.left_gaze_vector_endpoint_fr_xyz[
            self.current_frame_number - self.tail_length : self.current_frame_number, :
        ]
        self.left_gaze_laser_tail_line_item.setData(pos=this_left_gaze_laser_tail)

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
        self.start()

    def move_data_to_origin(self):
        mean_position_xyz = np.nanmedian(
            np.nanmedian(self.mediapipe_fr_mar_xyz, axis=0), axis=0
        )

        self.mediapipe_fr_mar_xyz[:, :, 0] -= mean_position_xyz[0]
        self.mediapipe_fr_mar_xyz[:, :, 1] -= mean_position_xyz[1]
        self.mediapipe_fr_mar_xyz[:, :, 2] -= mean_position_xyz[2]

        self.session_data.head_rotation_data.local_origin_fr_xyz[
            :, 0
        ] -= mean_position_xyz[0]
        self.session_data.head_rotation_data.local_origin_fr_xyz[
            :, 1
        ] -= mean_position_xyz[1]
        self.session_data.head_rotation_data.local_origin_fr_xyz[
            :, 2
        ] -= mean_position_xyz[2]

        if self.session_data.right_gaze_vector_endpoint_fr_xyz is not None:
            self.session_data.right_gaze_vector_endpoint_fr_xyz[
                :, 0
            ] -= mean_position_xyz[0]
            self.session_data.right_gaze_vector_endpoint_fr_xyz[
                :, 1
            ] -= mean_position_xyz[1]
            self.session_data.right_gaze_vector_endpoint_fr_xyz[
                :, 2
            ] -= mean_position_xyz[2]

            self.session_data.left_gaze_vector_endpoint_fr_xyz[
                :, 0
            ] -= mean_position_xyz[0]
            self.session_data.left_gaze_vector_endpoint_fr_xyz[
                :, 1
            ] -= mean_position_xyz[1]
            self.session_data.left_gaze_vector_endpoint_fr_xyz[
                :, 2
            ] -= mean_position_xyz[2]


if __name__ == "__main__":
    # session_id = 'sesh_2022-02-15_11_54_28_pupil_maybe'
    session_id = "sesh_2022-05-03_13_43_00_JSM_treadmill_day2_t0"
    data_path = Path("C:/Users/jonma/Dropbox/FreeMoCapProject/FreeMocap_Data/")
    session_path = data_path / session_id

    session_data_loader = SessionDataLoader(session_path)
    mediapipe_skel_fr_mar_xyz_in = session_data_loader.load_mediapipe_data(
        move_to_origin=True
    )
    print(f"mediapipe_skel_fr_mar_xyz.shape: {mediapipe_skel_fr_mar_xyz_in.shape}")
    qt_gl_laser_skeleton = QtGlLaserSkeletonVisualizer(
        mediapipe_skel_fr_mar_xyz=mediapipe_skel_fr_mar_xyz_in,
    )
    qt_gl_laser_skeleton.start_animation()
