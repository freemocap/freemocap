import logging

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

        # zero everything out, aka pin it to the origin, aka "subtract the position of the thing you want to be the origin from everything else", aka "do the thing that makes the X,Y,Z coordinates of the thing that should be (0,0,0) equal to (0,0,0)"
        nose_xyz_z = pin_point_new_origin(nose_xyz, head_center_xyz)
        left_ear_xyz_z = pin_point_new_origin(left_ear_xyz, head_center_xyz)

        # normalize the length of the vectors (so that each one is a unit vector)
        z_norm_nose_xyz = normalize_length(nose_xyz_z)
        z_norm_left_ear_xyz = normalize_length(left_ear_xyz_z)

        # define x_hat as the zero'd and normalized nose vector (i.e. the +X axis of the head starts at the head center and goes out the person's nose)
        x_hat_xyz = z_norm_nose_xyz

        # define z_hat as x_hat crossed with the normalized left ear vector
        # create `z_hat` a vector perpendicular to `x_hat` and the vector from the nose to the left ear(aka. the pseudo y_hat)
        z_hat_xyz = np.cross(x_hat_xyz, z_norm_left_ear_xyz)

        # define y_hat as z_hat cross with x_hat (this ensures that they are all orthogonal, where as the original vector to the left ear probably wasn't)
        y_hat_xyz = np.cross(x_hat_xyz, z_hat_xyz)
        # not sure if this needs normalizing, but it couldn't hurt
        y_hat_xyz = y_hat_xyz / np.linalg.norm(y_hat_xyz, axis=1)[:, None]

        self.head_rotation_matricies = [np.dstack((this_x_hat_xyz, this_y_hat_xyz, this_z_hat_xyz))
                                        for this_x_hat_xyz, this_y_hat_xyz, this_z_hat_xyz in
                                        zip(x_hat_xyz, y_hat_xyz, z_hat_xyz)]

        self.x_hat_xyz = x_hat_xyz
        self.y_hat_xyz = y_hat_xyz
        self.z_hat_xyz = z_hat_xyz

        if debug:
            self.show_debug_plot()

        return self.head_rotation_matricies

    def show_debug_plot(self):
        test_point_xyz_og = np.array((1, 1, 1))
        test_point_xyz_rot = np.empty(self.z_hat_xyz.shape)

        for frame_number in range(len(self.head_rotation_matricies)):
            # see https://peps.python.org/pep-0465/ for explanation of the `@` operator (which is a "matrix multiplication" operator)
            test_point_xyz_rot[frame_number, :] = self.head_rotation_matricies[frame_number] @ test_point_xyz_og

        plt.close('all')

        fig = plt.figure(num=124)
        fig.suptitle('Head Rotation Matrix - Debug Plot - Press ESC to Quit')
        ax = fig.add_subplot(111, projection='3d')

        ax_range = 2

        for frame_number in range(1200, self.x_hat_xyz.shape[0]):
            ax.clear()

            # plot head orthonormal basis vectors
            ax.plot(self.x_hat_xyz[frame_number - 30:frame_number, 0],
                    self.x_hat_xyz[frame_number - 30:frame_number, 1],
                    self.x_hat_xyz[frame_number - 30:frame_number, 2], 'r-')

            ax.plot(self.y_hat_xyz[frame_number - 30:frame_number, 0],
                    self.y_hat_xyz[frame_number - 30:frame_number, 1],
                    self.y_hat_xyz[frame_number - 30:frame_number, 2], 'g-')

            ax.plot(self.z_hat_xyz[frame_number - 30:frame_number, 0],
                    self.z_hat_xyz[frame_number - 30:frame_number, 1],
                    self.z_hat_xyz[frame_number - 30:frame_number, 2], 'b-')

            ax.plot([0, self.x_hat_xyz[frame_number, 0]],
                    [0, self.x_hat_xyz[frame_number, 1]],
                    [0, self.x_hat_xyz[frame_number, 2]], 'r-o', label='x_hat')

            ax.plot([0, self.y_hat_xyz[frame_number, 0]],
                    [0, self.y_hat_xyz[frame_number, 1]],
                    [0, self.y_hat_xyz[frame_number, 2]], 'g-o', label='y_hat')

            ax.plot([0, self.z_hat_xyz[frame_number, 0]],
                    [0, self.z_hat_xyz[frame_number, 1]],
                    [0, self.z_hat_xyz[frame_number, 2]], 'b-o', label='z_hat')

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

