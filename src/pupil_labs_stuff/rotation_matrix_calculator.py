import logging
from typing import List

import keyboard
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from jon_scratch.pupil_calibration_pipeline.data_classes.rotation_data_class import (
    RotationDataClass,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

matplotlib.use("qt5agg")


def pin_point_new_origin(point_xyz, new_origin_xyz):
    return point_xyz - new_origin_xyz


def normalize_length(point_xyz):
    return point_xyz / get_norm_length(point_xyz, axis=1)[:, None]


def get_norm_length(point_xyz, axis=1):
    return np.linalg.norm(point_xyz, axis=axis)


class RotationMatrixCalculator:
    mediapipe_skeleton_fr_mar_xyz: np.ndarray

    def __init__(self, mediapipe_skeleton_fr_mar_xyz):
        self.mediapipe_skeleton_fr_mar_xyz = mediapipe_skeleton_fr_mar_xyz

    def calculate_head_rotation_matricies(
        self, normalize_length_by_x: bool = False, debug: bool = False
    ):
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
        left_ear_id = 7
        right_ear_id = 8

        nose_xyz = self.mediapipe_skeleton_fr_mar_xyz[:, nose_id, :].copy()
        right_ear_xyz = self.mediapipe_skeleton_fr_mar_xyz[:, right_ear_id, :].copy()
        left_ear_xyz = self.mediapipe_skeleton_fr_mar_xyz[:, left_ear_id, :].copy()
        head_center_xyz = (right_ear_xyz + left_ear_xyz) / 2

        head_rotation_data = self.define_basis_vectors(
            center_point_fr_xyz=head_center_xyz,
            x_direction_fr_xyz=nose_xyz,
            y_direction_fr_xyz=left_ear_xyz,
            normalize_length_by_x=normalize_length_by_x,
        )
        if debug:
            self.show_head_rotation_debug_plot(head_rotation_data)

        return head_rotation_data

    def calculate_eye_rotation_matricies(
        self,
        eye: str,
        normalize_length_by_x: bool = False,
        debug: bool = False,
    ) -> List[np.ndarray]:
        nose_index = 0
        if eye == "left":
            inner_eye_index = 1
            eye_mid_index = 2
            outer_eye_index = 3
            x_direction_fr_xyz = self.mediapipe_skeleton_fr_mar_xyz[
                :, inner_eye_index, :
            ]  # this will make Z+ point forward
        elif eye == "right":
            inner_eye_index = 4
            eye_mid_index = 5
            outer_eye_index = 6
            x_direction_fr_xyz = self.mediapipe_skeleton_fr_mar_xyz[
                :, outer_eye_index, :
            ]  # this will make Z+ point forward
        else:
            raise ValueError('`eye` must be "left" or "right"')

        y_direction_fr_xyz = self.mediapipe_skeleton_fr_mar_xyz[:, nose_index, :]

        eye_mid_fr_xyz = self.mediapipe_skeleton_fr_mar_xyz[:, eye_mid_index, :]

        eye_socket_rotation_data = self.define_basis_vectors(
            center_point_fr_xyz=eye_mid_fr_xyz,
            x_direction_fr_xyz=x_direction_fr_xyz,
            y_direction_fr_xyz=y_direction_fr_xyz,
            normalize_length_by_x=normalize_length_by_x,
        )

        return eye_socket_rotation_data

    def define_basis_vectors(
        self,
        center_point_fr_xyz: np.ndarray = None,
        x_direction_fr_xyz: np.ndarray = None,
        y_direction_fr_xyz: np.ndarray = None,
        z_direction_fr_xyz: np.ndarray = None,
        normalize_length_by_x: bool = True,
    ) -> RotationDataClass:
        """
        create orthonormal basis vectors based on a center point and at least TWO of the following =  a point defining X direction, a point defining Y direction, and a point defining Z direction
        """

        x_known = True
        y_known = True
        z_known = True

        if x_direction_fr_xyz is None:
            x_known = False
            x_direction_fr_xyz = np.empty(center_point_fr_xyz.shape)
            x_direction_fr_xyz[:] = np.nan

        if y_direction_fr_xyz is None:
            y_known = False
            y_direction_fr_xyz = np.empty(center_point_fr_xyz.shape)
            y_direction_fr_xyz[:] = np.nan

        if z_direction_fr_xyz is None:
            z_known = False
            z_direction_fr_xyz = np.empty(center_point_fr_xyz.shape)
            z_direction_fr_xyz[:] = np.nan

        if sum([x_known, y_known, z_known]) < 2:
            raise ValueError(
                "Must specify at least two of the following: x_direction_fr_xyz, y_direction_fr_xyz, z_direction_fr_xyz"
            )

        if (
            center_point_fr_xyz is not None
        ):  # if center point is specified, then use it to zero out the x,y,z directions vectors
            zero_x_direction_xyz = pin_point_new_origin(
                x_direction_fr_xyz, center_point_fr_xyz
            )
            zero_y_direction_xyz = pin_point_new_origin(
                y_direction_fr_xyz, center_point_fr_xyz
            )
            zero_z_direction_xyz = pin_point_new_origin(
                z_direction_fr_xyz, center_point_fr_xyz
            )
        else:
            zero_x_direction_xyz = x_direction_fr_xyz
            zero_y_direction_xyz = y_direction_fr_xyz
            zero_z_direction_xyz = z_direction_fr_xyz

        x_hat_xyz = None
        y_hat_xyz = None
        z_hat_xyz = None

        if x_known:
            x_norm_length = np.nanmean(get_norm_length(zero_x_direction_xyz))
            x_hat_xyz = normalize_length(zero_x_direction_xyz)
            if y_known:  # we know x and y directions and need to find Z by X cross Y
                z_hat_xyz = normalize_length(np.cross(x_hat_xyz, zero_y_direction_xyz))
                y_hat_xyz = normalize_length(np.cross(z_hat_xyz, x_hat_xyz))

            else:  # we know x and z directions and need to find Y by Z cross X
                y_hat_xyz = normalize_length(np.cross(zero_z_direction_xyz, x_hat_xyz))
                z_hat_xyz = normalize_length(np.cross(x_hat_xyz, y_hat_xyz))

        elif y_known:  # we know y and z directions and need to find X by Y cross Z
            y_hat_xyz = normalize_length(zero_y_direction_xyz)
            x_hat_xyz = normalize_length(np.cross(y_hat_xyz, zero_z_direction_xyz))
            z_hat_xyz = normalize_length(np.cross(x_hat_xyz, y_hat_xyz))

        if normalize_length_by_x:
            x_hat_xyz = x_hat_xyz * x_norm_length
            y_hat_xyz = y_hat_xyz * x_norm_length
            z_hat_xyz = z_hat_xyz * x_norm_length

        # #umm, this shouldn't be necessary.... but it makes it work, so....
        # x_hat_xyz = -x_hat_xyz
        # y_hat_xyz = -y_hat_xyz
        # z_hat_xyz = z_hat_xyz

        # create 3x3 cosine rotation matricies by stacking X_hat, Y_hat, and Z_hat
        rotation_matricies = []
        frame_number = -1
        for this_x_hat_xyz, this_y_hat_xyz, this_z_hat_xyz in zip(
            x_hat_xyz, y_hat_xyz, z_hat_xyz
        ):
            frame_number += 1
            if frame_number > 1000:
                f = 9
            this_rotation_matrix = np.squeeze(
                np.dstack((this_x_hat_xyz, this_y_hat_xyz, this_z_hat_xyz))
            )

            assert this_rotation_matrix.shape == (3, 3)

            if not np.isnan(this_x_hat_xyz).any():
                assert (this_rotation_matrix[:, 0] == this_x_hat_xyz).all()

            rotation_matricies.append(this_rotation_matrix)

        rotation_matricies = [
            np.transpose(this_rotation_martix)
            for this_rotation_martix in rotation_matricies
        ]

        return RotationDataClass(
            rotation_matricies=rotation_matricies,
            local_origin_fr_xyz=center_point_fr_xyz,
            x_hat_norm_fr_xyz=x_hat_xyz,
            y_hat_norm_fr_xyz=y_hat_xyz,
            z_hat_norm_fr_xyz=z_hat_xyz,
        )

    def show_head_rotation_debug_plot(self, rotation_data: RotationDataClass):
        rotation_matricies = rotation_data.rotation_matricies
        local_origin_fr_xyz = rotation_data.local_origin_fr_xyz

        x_hat_xyz = np.asarray(
            [this_rot_mat[0, :] for this_rot_mat in rotation_matricies]
        )
        y_hat_xyz = np.asarray(
            [this_rot_mat[1, :] for this_rot_mat in rotation_matricies]
        )
        z_hat_xyz = np.asarray(
            [this_rot_mat[2, :] for this_rot_mat in rotation_matricies]
        )

        test_point_xyz_og = np.array((1, 1, 1))
        test_point_xyz_rot = np.empty(z_hat_xyz.shape)
        logger.warning(
            "We shouldnt have to transpose the rotation matix here, need to fix this upstream"
        )

        for frame_number in range(len(rotation_matricies)):
            # see https://peps.python.org/pep-0465/ for explanation of the `@` operator (which is a "matrix multiplication" operator)
            test_point_xyz_rot[frame_number, :] = (
                np.transpose(rotation_matricies[frame_number]) @ test_point_xyz_og
            )

        z_mediapipe_skeleton_fr_mar_xyz = np.empty(
            self.mediapipe_skeleton_fr_mar_xyz.shape
        )
        for this_marker_number in range(self.mediapipe_skeleton_fr_mar_xyz.shape[1]):
            z_mediapipe_skeleton_fr_mar_xyz[
                :, this_marker_number, :
            ] = pin_point_new_origin(
                self.mediapipe_skeleton_fr_mar_xyz[:, this_marker_number, :],
                local_origin_fr_xyz,
            )
        plt.close("all")

        fig = plt.figure(num=124)
        fig.suptitle("Head Rotation Matrix - Debug Plot - Press ESC to Quit")
        ax = fig.add_subplot(111, projection="3d")

        ax_range = np.nanmean(get_norm_length(x_hat_xyz)) * 2

        for frame_number in range(1200, x_hat_xyz.shape[0]):
            ax.clear()

            # plot head orthonormal basis vectors
            ax.plot(
                x_hat_xyz[frame_number - 30 : frame_number, 0],
                x_hat_xyz[frame_number - 30 : frame_number, 1],
                x_hat_xyz[frame_number - 30 : frame_number, 2],
                "r-",
            )

            ax.plot(
                y_hat_xyz[frame_number - 30 : frame_number, 0],
                y_hat_xyz[frame_number - 30 : frame_number, 1],
                y_hat_xyz[frame_number - 30 : frame_number, 2],
                "g-",
            )

            ax.plot(
                z_hat_xyz[frame_number - 30 : frame_number, 0],
                z_hat_xyz[frame_number - 30 : frame_number, 1],
                z_hat_xyz[frame_number - 30 : frame_number, 2],
                "b-",
            )

            ax.plot(
                [0, x_hat_xyz[frame_number, 0]],
                [0, x_hat_xyz[frame_number, 1]],
                [0, x_hat_xyz[frame_number, 2]],
                "r-o",
                label="x_hat",
            )

            ax.plot(
                [0, y_hat_xyz[frame_number, 0]],
                [0, y_hat_xyz[frame_number, 1]],
                [0, y_hat_xyz[frame_number, 2]],
                "g-o",
                label="y_hat",
            )

            ax.plot(
                [0, z_hat_xyz[frame_number, 0]],
                [0, z_hat_xyz[frame_number, 1]],
                [0, z_hat_xyz[frame_number, 2]],
                "b-o",
                label="z_hat",
            )

            # plot test point rotated with head rotation matricies

            ax.plot(
                test_point_xyz_rot[frame_number - 30 : frame_number, 0],
                test_point_xyz_rot[frame_number - 30 : frame_number, 1],
                test_point_xyz_rot[frame_number - 30 : frame_number, 2],
                "k-",
            )

            ax.plot(
                [0, test_point_xyz_rot[frame_number, 0]],
                [0, test_point_xyz_rot[frame_number, 1]],
                [0, test_point_xyz_rot[frame_number, 2]],
                "k-o",
                label="test point",
            )

            # plot a friendly skeleton
            ax.scatter(
                z_mediapipe_skeleton_fr_mar_xyz[frame_number, :, 0],
                z_mediapipe_skeleton_fr_mar_xyz[frame_number, :, 1],
                z_mediapipe_skeleton_fr_mar_xyz[frame_number, :, 2],
                "ko",
            )

            ax.set_xlim([-ax_range, ax_range])
            ax.set_ylim([-ax_range, ax_range])
            ax.set_zlim([-ax_range, ax_range])

            ax.legend()
            plt.pause(0.01)

            if keyboard.is_pressed("esc"):
                print("You Pressed Escape!")
                break  # finishing the loop

        plt.close(fig)
