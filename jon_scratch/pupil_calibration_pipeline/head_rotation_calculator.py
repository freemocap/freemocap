import logging
from typing import List

import numpy as np

import matplotlib.pyplot as plt
import matplotlib
import keyboard

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

matplotlib.use('qt5agg')


def pin_point_new_origin(point_xyz, new_origin_xyz):
    return point_xyz - new_origin_xyz


def normalize_length(point_xyz):
    return point_xyz / np.linalg.norm(point_xyz, axis=1)[:, None]


class HeadRotationCalculator:
    mediapipe_skeleton_fr_mar_xyz: np.ndarray

    def __init__(self, mediapipe_skeleton_fr_mar_xyz):
        self.mediapipe_skeleton_fr_mar_xyz = mediapipe_skeleton_fr_mar_xyz

    def calculate_head_rotation_matricies(self, debug=False):
        """
        # Calculate head rotation matricies

        calculate orthonormal basis vectors of the head on each frame, stack them on top of each other to make 3x3 rotation matricies, because apparently that's how that works?!

        1 - calculate `head_center_xyz` as mean of left and right ear markers
        2 - define x+ as vector between `head_center_xyz` and `nose_xyz`- normalize to get `x_hat`
        3 - define y+ as vector between `head_center_xyz` and `left_ear_xyz` - normalize to get `y_hat_temp` (will be replaced later, to ensure orthogonal \)
        4 - define z+ as cross product of `x_hat` and `y_hat`
        5 - replace `y_hat_temp` with `z_hat` crossed wtih `x_hat` (Pretty sure that makes it right handed...)

        Stack x_hat, y_hat, and z_hat on top of each other, and that's your head rotation matrix on that frame

        """
        nose_id = 0
        right_ear_id = 8
        left_ear_id = 7

        nose_xyz = self.mediapipe_skeleton_fr_mar_xyz[:, nose_id, :]
        right_ear_xyz = self.mediapipe_skeleton_fr_mar_xyz[:, right_ear_id, :]
        left_ear_xyz = self.mediapipe_skeleton_fr_mar_xyz[:, left_ear_id, :]
        head_center_xyz = (right_ear_xyz + left_ear_xyz) / 2

        head_rotation_matricies = self.define_orthonormal_basis_vectors(center_point_fr_xyz=head_center_xyz,
                                                                        x_direction_fr_xyz=nose_xyz,
                                                                        y_direction_fr_xyz=left_ear_xyz)
        if debug:
            self.show_head_rotation_debug_plot(head_rotation_matricies)

        return head_rotation_matricies

    def define_orthonormal_basis_vectors(self,
                                         center_point_fr_xyz: np.ndarray = None,
                                         x_direction_fr_xyz: np.ndarray = None,
                                         y_direction_fr_xyz: np.ndarray = None,
                                         z_direction_fr_xyz: np.ndarray = None) -> List[np.ndarray]:
        """
        create orthonormal basis vectors based on a center point and at least TWO of the following =  a point defining X direction, a point defining Y direction, and a point defining Z direction
        """

        x_unknown = False
        y_unknown = False
        z_unknown = False

        if x_direction_fr_xyz is None:
            x_unknown = True
            x_direction_fr_xyz = np.empty(center_point_fr_xyz.shape)
            x_direction_fr_xyz[:] = np.nan
        if y_direction_fr_xyz is None:
            y_unknown = True
            y_direction_fr_xyz = np.empty(center_point_fr_xyz.shape)
            y_direction_fr_xyz[:] = np.nan
        if z_direction_fr_xyz is None:
            z_unknown = True
            z_direction_fr_xyz = np.empty(center_point_fr_xyz.shape)
            z_direction_fr_xyz[:] = np.nan

        if sum([x_unknown, y_unknown, z_unknown]) > 1:
            raise ValueError(
                "Must specify at least two of the following: x_direction_fr_xyz, y_direction_fr_xyz, z_direction_fr_xyz")

        if center_point_fr_xyz is not None:  # if center point is specified, then use it to zero out the x,y,z directions vectors
            zero_x_direction_xyz = pin_point_new_origin(center_point_fr_xyz, x_direction_fr_xyz)
            zero_y_direction_xyz = pin_point_new_origin(center_point_fr_xyz, y_direction_fr_xyz)
            zero_z_direction_xyz = pin_point_new_origin(center_point_fr_xyz, z_direction_fr_xyz)
        else:
            zero_x_direction_xyz = x_direction_fr_xyz
            zero_y_direction_xyz = y_direction_fr_xyz
            zero_z_direction_xyz = z_direction_fr_xyz

        x_hat_xyz = None
        y_hat_xyz = None
        z_hat_xyz = None

        if not x_unknown:
            x_hat_xyz = normalize_length(zero_x_direction_xyz)
            if not y_unknown:  # we know x and y directions and need to find Z by X cross Y
                z_hat_xyz = normalize_length(np.cross(x_hat_xyz, zero_y_direction_xyz))
                y_hat_xyz = normalize_length(np.cross(z_hat_xyz, x_hat_xyz))

            else:  # we know x and z directions and need to find Y by Z cross X
                y_hat_xyz = normalize_length(np.cross(zero_y_direction_xyz, x_hat_xyz))
                z_hat_xyz = normalize_length(np.cross(x_hat_xyz, y_hat_xyz))

        elif not y_unknown:  # we know y and z directions and need to find X by Y cross Z
            y_hat_xyz = normalize_length(zero_y_direction_xyz)
            x_hat_xyz = normalize_length(np.cross(y_hat_xyz, zero_z_direction_xyz))
            z_hat_xyz = normalize_length(np.cross(x_hat_xyz, y_hat_xyz))

        # create 3x3 cosine rotation matricies by stacking X_hat, Y_hat, and Z_hat
        rotation_matricies = [np.vstack((this_x_hat_xyz, this_y_hat_xyz, this_z_hat_xyz))
                              for this_x_hat_xyz, this_y_hat_xyz, this_z_hat_xyz in
                              zip(x_hat_xyz, y_hat_xyz, z_hat_xyz)]

        rotation_matricies = [this_rotation_martix.T for this_rotation_martix in rotation_matricies]

        return rotation_matricies

    def create_unrotated_gaze_laser(self, debug, eye: str) -> np.ndarray:
        nose_index = 0
        if eye == 'left':
            inner_eye_index = 1
            eye_mid_index = 2
            outer_eye_index = 3
            x_direction_fr_xyz = self.mediapipe_skeleton_fr_mar_xyz[:, inner_eye_index,
                                 :]  # this will make Z+ point forward
        if eye == 'right':
            inner_eye_index = 4
            eye_mid_index = 5
            outer_eye_index = 6
            x_direction_fr_xyz = self.mediapipe_skeleton_fr_mar_xyz[:, outer_eye_index,
                                 :]  # this will make Z+ point forward

        y_direction_fr_xyz = self.mediapipe_skeleton_fr_mar_xyz[:, nose_index, :]

        eye_mid_fr_xyz = self.mediapipe_skeleton_fr_mar_xyz[:, eye_mid_index, :]

        eye_socket_rotation_matricies = self.define_orthonormal_basis_vectors(center_point_fr_xyz=eye_mid_fr_xyz,
                                                                       x_direction_fr_xyz=x_direction_fr_xyz,
                                                                       y_direction_fr_xyz=y_direction_fr_xyz)

        initial_eye_laser_unit_vector = np.array([0, 0, 1])
        eye_laser_unit_vectors_fr_xyz = [this_eye_socket_rotation_matrix.T @ initial_eye_laser_unit_vector for this_eye_socket_rotation_matrix in eye_socket_rotation_matricies]

        eye_laser_unit_vectors_fr_xyz *= 1000 #make it a meter long
        eye_laser_unit_vectors_fr_xyz += eye_mid_fr_xyz #situation gaze lasers onto eye_mid_fr_xyz

        return eye_laser_unit_vectors_fr_xyz  # this is a unit vector pointing outward from eyeball center (as if eyes were paralyzed in center of their orbits)

    def show_head_rotation_debug_plot(self, head_rotation_matricies):

        x_hat_xyz = np.asarray([this_rot_mat[0, :] for this_rot_mat in head_rotation_matricies])
        y_hat_xyz = np.asarray([this_rot_mat[1, :] for this_rot_mat in head_rotation_matricies])
        z_hat_xyz = np.asarray([this_rot_mat[2, :] for this_rot_mat in head_rotation_matricies])

        test_point_xyz_og = np.array((1, 1, 1))
        test_point_xyz_rot = np.empty(z_hat_xyz.shape)
        logger.warning('We shouldnt have to transpose the rotation matix here, need to fix this upstream')

        for frame_number in range(len(head_rotation_matricies)):
            # see https://peps.python.org/pep-0465/ for explanation of the `@` operator (which is a "matrix multiplication" operator)
            test_point_xyz_rot[frame_number, :] = head_rotation_matricies[frame_number].T @ test_point_xyz_og

        plt.close('all')

        fig = plt.figure(num=124)
        fig.suptitle('Head Rotation Matrix - Debug Plot - Press ESC to Quit')
        ax = fig.add_subplot(111, projection='3d')

        ax_range = 2

        for frame_number in range(1200, x_hat_xyz.shape[0]):
            ax.clear()

            # plot head orthonormal basis vectors
            ax.plot(x_hat_xyz[frame_number - 30:frame_number, 0],
                    x_hat_xyz[frame_number - 30:frame_number, 1],
                    x_hat_xyz[frame_number - 30:frame_number, 2], 'r-')

            ax.plot(y_hat_xyz[frame_number - 30:frame_number, 0],
                    y_hat_xyz[frame_number - 30:frame_number, 1],
                    y_hat_xyz[frame_number - 30:frame_number, 2], 'g-')

            ax.plot(z_hat_xyz[frame_number - 30:frame_number, 0],
                    z_hat_xyz[frame_number - 30:frame_number, 1],
                    z_hat_xyz[frame_number - 30:frame_number, 2], 'b-')

            ax.plot([0, x_hat_xyz[frame_number, 0]],
                    [0, x_hat_xyz[frame_number, 1]],
                    [0, x_hat_xyz[frame_number, 2]], 'r-o', label='x_hat')

            ax.plot([0, y_hat_xyz[frame_number, 0]],
                    [0, y_hat_xyz[frame_number, 1]],
                    [0, y_hat_xyz[frame_number, 2]], 'g-o', label='y_hat')

            ax.plot([0, z_hat_xyz[frame_number, 0]],
                    [0, z_hat_xyz[frame_number, 1]],
                    [0, z_hat_xyz[frame_number, 2]], 'b-o', label='z_hat')

            # plot test point rotated with head rotation matricies

            ax.plot(test_point_xyz_rot[frame_number - 30:frame_number, 0],
                    test_point_xyz_rot[frame_number - 30:frame_number, 1],
                    test_point_xyz_rot[frame_number - 30:frame_number, 2], 'k-')

            ax.plot([0, test_point_xyz_rot[frame_number, 0]],
                    [0, test_point_xyz_rot[frame_number, 1]],
                    [0, test_point_xyz_rot[frame_number, 2]], 'k-o', label='test point')

            ax.set_xlim([-ax_range, ax_range])
            ax.set_ylim([-ax_range, ax_range])
            ax.set_zlim([-ax_range, ax_range])

            ax.legend()
            plt.pause(.01)

            if keyboard.is_pressed('esc'):
                print('You Pressed Escape!')
                break  # finishing the loop

        plt.close(fig)
