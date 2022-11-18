import logging
from typing import Union, List

import keyboard
import numpy as np
from scipy import optimize
from matplotlib import pyplot as plt
import matplotlib
from scipy.spatial.transform import Rotation

from jon_scratch.pupil_calibration_pipeline.data_classes.freemocap_session_data_class import (
    FreemocapSessionDataClass,
)
from jon_scratch.pupil_calibration_pipeline.data_classes.pupil_dataclass_and_handler import (
    PupilLabsDataClass,
)
from jon_scratch.pupil_calibration_pipeline.data_classes.rotation_data_class import (
    RotationDataClass,
)
from jon_scratch.pupil_calibration_pipeline.spherical_coordiate_converters.cart2sph_and_sph2cart import (
    cart2sph,
    sph2cart,
)

matplotlib.use("qt5agg")
logger = logging.getLogger(__name__)


class VorCalibrator:
    """
    Calibrate synchronized eye data from a Pupil Labs eye tracker with FreeMoCap skeleton
    see methods sections of (Matthis, Yates, and Hayhoe, Current Biology, 2018) and (Matthis, Muller, Bonnen, Hayehoe, PLoS Computation Biology 2022) for details
    """

    def __init__(
        self,
        mediapipe_skel_fr_mar_xyz: np.ndarray,
        vor_start_frame: int = None,
        vor_end_frame: int = None,
        debug: bool = False,
    ):
        self.debug = debug
        self.mediapipe_skel_fr_mar_xyz = mediapipe_skel_fr_mar_xyz
        if vor_start_frame is not None:
            self.vor_start_frame = vor_start_frame
            if vor_end_frame is None:
                raise ValueError(
                    "Must specify vor_end_frame if vor_start_frame is specified"
                )
            self.vor_end_frame = vor_end_frame

    def calibrate(
        self,
        pupil_labs_eye_data: PupilLabsDataClass,
        eye_socket_rotation_data: RotationDataClass,
        head_rotation_data: RotationDataClass,
        fixation_point_fr_xyz: np.ndarray,
    ) -> np.ndarray:

        if not fixation_point_fr_xyz.shape[1] == 3:
            raise Exception(
                "fixation_point_fr_xyz must be a numpy array with 3 columns"
            )

        eye_socket_origin_fr_xyz = eye_socket_rotation_data.local_origin_fr_xyz
        eye_socket_rotation_matricies = eye_socket_rotation_data.rotation_matricies

        head_rotation_matricies = head_rotation_data.rotation_matricies

        # gaze_unit_vector_end_point_fr_xyz = eye_socket_rotation_data.z_hat_norm_fr_xyz
        self.fixation_distance = self.get_distance_between_two_points(
            fixation_point_fr_xyz,
            eye_socket_origin_fr_xyz[self.vor_start_frame : self.vor_end_frame, :],
        )

        # not sure why I need to do this, but Karl Muller did it so it's likely necessary
        gaze_y = -pupil_labs_eye_data.pupil_center_normal_y
        gaze_x = pupil_labs_eye_data.pupil_center_normal_z
        gaze_z = pupil_labs_eye_data.pupil_center_normal_x

        gaze_x = gaze_x * np.nanmean(self.fixation_distance)
        gaze_y = gaze_y * np.nanmean(self.fixation_distance)
        gaze_z = gaze_z * np.nanmean(self.fixation_distance)

        use_dummy_gaze_data = False
        if use_dummy_gaze_data:
            gaze_x = np.zeros(
                pupil_labs_eye_data.pupil_center_normal_x.shape
            ) * np.nanmedian(self.fixation_distance)
            gaze_y = np.zeros(
                pupil_labs_eye_data.pupil_center_normal_y.shape
            ) * np.nanmedian(self.fixation_distance)
            gaze_z = np.ones(
                pupil_labs_eye_data.pupil_center_normal_z.shape
            ) * np.nanmedian(self.fixation_distance)

        self.uncalibrated_gaze_vector_endpoint_fr_xyz = self.rotate_gaze_lasers(
            [0, 0, 0],
            eye_socket_origin_fr_xyz,
            eye_socket_rotation_matricies,
            head_rotation_matricies,
            gaze_x,
            gaze_y,
            gaze_z,
        )

        self.calibrated_rotational_offset = self.calculate_optimal_rotational_offset(
            eye_socket_origin_fr_xyz,
            eye_socket_rotation_matricies,
            head_rotation_matricies,
            fixation_point_fr_xyz,
            gaze_x,
            gaze_y,
            gaze_z,
        )

        gaze_vector_endpoint_fr_xyz = self.rotate_gaze_lasers(
            self.calibrated_rotational_offset,
            eye_socket_origin_fr_xyz,
            eye_socket_rotation_matricies,
            head_rotation_matricies,
            gaze_x,
            gaze_y,
            gaze_z,
        )

        return gaze_vector_endpoint_fr_xyz

    def calculate_optimal_rotational_offset(
        self,
        eye_socket_origin_fr_xyz: np.ndarray,
        eye_socket_rotation_matricies: List[np.ndarray],
        head_rotation_matricies,
        fixation_point_fr_xyz: np.ndarray,
        gaze_x: np.ndarray,
        gaze_y: np.ndarray,
        gaze_z: np.ndarray,
    ) -> List[float]:
        """
        Calculate the optimal rotational offset to apply to Pupil Labs eye tracker data in order to minimize the distance
        between teh end of the gaze vector and the fixation point on each frame
        (based on the VOR calibration methods described in Matthis, Yates, and Hayhoe, Current Biology, 2018 and Matthis, Muller, Bonnen, Hayhoe, PLoS Computation Biology 2022)

        """
        initial_rotational_offset_guess = [0, 0, 0]

        vor_frames = np.arange(self.vor_start_frame, self.vor_end_frame)

        optimization_results = optimize.least_squares(
            self.get_error_for_a_given_rotational_offset_guess,
            initial_rotational_offset_guess,
            args=(
                eye_socket_origin_fr_xyz[vor_frames, :],
                eye_socket_rotation_matricies[
                    self.vor_start_frame : self.vor_end_frame
                ],
                head_rotation_matricies[self.vor_start_frame : self.vor_end_frame],
                fixation_point_fr_xyz,
                gaze_x[vor_frames],
                gaze_y[vor_frames],
                gaze_z[vor_frames],
            ),
            gtol=1e-10,
            verbose=2,
        )
        calibrated_rotational_offset = optimization_results.x
        return calibrated_rotational_offset

    def get_error_for_a_given_rotational_offset_guess(
        self,
        rotational_offset_guess,
        eye_socket_origin_fr_xyz,
        eye_socket_rotation_matricies,
        head_rotation_matricies,
        fixation_point_fr_xyz,
        gaze_x,
        gaze_y,
        gaze_z,
    ):

        gaze_laser_endpoint_during_vor_fr_xyz = self.rotate_gaze_lasers(
            rotational_offset_guess,
            eye_socket_origin_fr_xyz,
            eye_socket_rotation_matricies,
            head_rotation_matricies,
            gaze_x,
            gaze_y,
            gaze_z,
        )

        distance_between_gaze_endpoint_and_fixation_point_fr_xyz = (
            self.get_distance_between_two_points(
                gaze_laser_endpoint_during_vor_fr_xyz, fixation_point_fr_xyz
            )
        )
        distance_error = np.sqrt(
            np.nanmean(distance_between_gaze_endpoint_and_fixation_point_fr_xyz**2)
        )

        gaze_tip_velocity_fr_xyz = np.diff(
            gaze_laser_endpoint_during_vor_fr_xyz, axis=0
        )
        mean_gaze_tip_velocity_per_frame = np.nanmean(gaze_tip_velocity_fr_xyz, axis=0)
        velocity_error = np.sqrt(np.nanmean(mean_gaze_tip_velocity_per_frame**2))

        error = distance_error + velocity_error

        if self.debug:
            self.plot_optimization_error(
                error,
                gaze_laser_endpoint_during_vor_fr_xyz,
                eye_socket_origin_fr_xyz,
                fixation_point_fr_xyz,
            )
        return error

    def plot_optimization_error(
        self,
        error,
        gaze_laser_endpoint_during_vor_fr_xyz,
        eye_socket_origin_fr_xyz,
        fixation_point_fr_xyz,
    ):
        figure_number = 13451

        if not plt.fignum_exists(figure_number):
            fig = plt.figure(figure_number)
            ax = fig.add_subplot(111, projection="3d")
        else:
            fig = plt.gcf()
            ax = plt.gca()

        mean_eye_origin_x = np.nanmean(eye_socket_origin_fr_xyz[:, 0])
        mean_eye_origin_y = np.nanmean(eye_socket_origin_fr_xyz[:, 1])
        mean_eye_origin_z = np.nanmean(eye_socket_origin_fr_xyz[:, 2])

        fig.suptitle(f"error: {error}")
        ax_range = 1e3
        ax.clear()

        ax.plot(
            mean_eye_origin_x,
            mean_eye_origin_y,
            mean_eye_origin_z,
            "mh",
            label="mean eye origin",
        )

        ax.plot(
            self.uncalibrated_gaze_vector_endpoint_fr_xyz[
                self.vor_start_frame : self.vor_end_frame, 0
            ],
            self.uncalibrated_gaze_vector_endpoint_fr_xyz[
                self.vor_start_frame : self.vor_end_frame, 1
            ],
            self.uncalibrated_gaze_vector_endpoint_fr_xyz[
                self.vor_start_frame : self.vor_end_frame, 2
            ],
            "k-o",
            label="original gaze xyz",
        )

        ax.plot(
            gaze_laser_endpoint_during_vor_fr_xyz[:, 0],
            gaze_laser_endpoint_during_vor_fr_xyz[:, 1],
            gaze_laser_endpoint_during_vor_fr_xyz[:, 2],
            "r-o",
            label="gaze_rotated_by_guess_then_head_rotation_xyz",
        )

        ax.plot(
            fixation_point_fr_xyz[:, 0],
            fixation_point_fr_xyz[:, 1],
            fixation_point_fr_xyz[:, 2],
            "b-o",
            label="mean_fixation_point_xyz",
        )

        ax.set_xlim([mean_eye_origin_x - ax_range, mean_eye_origin_x + ax_range])
        ax.set_ylim([mean_eye_origin_y - ax_range, mean_eye_origin_y + ax_range])
        ax.set_zlim([mean_eye_origin_z - ax_range, mean_eye_origin_z + ax_range])
        ax.legend()
        plt.pause(0.01)

        if keyboard.is_pressed("esc"):
            print("You Pressed Escape!")
            self.debug = False
            plt.close(fig)

    def get_distance_between_two_points(
        self, local_origin_fr_xyz, fixation_point_fr_xyz
    ):
        return np.linalg.norm(local_origin_fr_xyz - fixation_point_fr_xyz, axis=1)

    def create_unrotated_gaze_lasers_from_eye_rotation_matrixies(
        self,
        gaze_vector_start_point_fr_xyz: np.ndarray,
        gaze_unit_vector_end_point_fr_xyz: np.ndarray,
        calbration_distance,
    ) -> np.ndarray:
        """
        Creates an unrotated gaze laser for each frame in the skeleton/gaze data. Returns a vector the same length as the calibration_distance, shooting our of the skeletons eye_sockets (as if they eyes were paralyzed).
        """
        if (
            not gaze_vector_start_point_fr_xyz.shape
            == gaze_unit_vector_end_point_fr_xyz.shape
        ):
            raise Exception(
                "`gaze_vector_start_point_fr_xyz` and `gaze_unit_vector_end_point_fr_xyz` must have the same shape"
            )

        # scale gaze vector so it's the same norm/length as the calibration distance
        gaze_unit_vector_end_point_fr_xyz = (
            gaze_unit_vector_end_point_fr_xyz * calbration_distance
        )

        # move it from an zero-centered reference frame to the eye socket reference frame
        gaze_vector_end_point_fr_xyz = (
            gaze_unit_vector_end_point_fr_xyz + gaze_vector_start_point_fr_xyz
        )

        return gaze_vector_end_point_fr_xyz

    def rotate_gaze_lasers(
        self,
        rotational_offset,
        gaze_vector_start_point_fr_xyz,
        eye_socket_rotation_matricies,
        head_rotation_matricies,
        gaze_x,
        gaze_y,
        gaze_z,
    ) -> np.ndarray:
        """ "
        - pin gaze to origin
        - rotate gaze vector by `calibrated_rotational_offset`
        - rotate by measured eye movemens (from pupil labs)
         - translate gaze vector back to the eye socket (by adding eyeball center xyz)
        """

        # - rotate gaze vector by `calibrated_rotational_offset`
        offset_x_euler = rotational_offset[0]
        offset_y_euler = rotational_offset[1]
        offset_z_euler = rotational_offset[2]
        offset_rotation_matrix_guess = Rotation.from_euler(
            "xyz", (offset_x_euler, offset_y_euler, offset_z_euler)
        ).as_matrix()

        original_gaze_fr_xyz = np.array([gaze_x, gaze_y, gaze_z])

        # rotate gaze vector by rotational offset to align pupil labs gaze with the eye sockets gaze
        gaze_rotated_by_guess_fr_xyz = [
            offset_rotation_matrix_guess @ original_gaze_fr_xyz[:, this_frame_number]
            for this_frame_number in range(original_gaze_fr_xyz.shape[1])
        ]
        gaze_rotated_by_guess_fr_xyz = np.array(gaze_rotated_by_guess_fr_xyz)

        # THEN rotate gaze vector by eye_socket_rotation_matrix to align it with the eye sockets gaze direction (i think)
        gaze_fr_xyz = [
            np.transpose(head_rotation_matricies[this_frame_number])
            @ gaze_rotated_by_guess_fr_xyz[this_frame_number, :]
            for this_frame_number in range(gaze_rotated_by_guess_fr_xyz.shape[0])
        ]
        gaze_fr_xyz = np.array(gaze_fr_xyz)

        # 6 - translate gaze vector back to the eye socket (by adding eyeball center xyz)
        gaze_laser_fr_xyz = np.empty(gaze_fr_xyz.shape)
        gaze_laser_fr_xyz[:, 0] = (
            gaze_fr_xyz[:, 0] + gaze_vector_start_point_fr_xyz[:, 0]
        )
        gaze_laser_fr_xyz[:, 1] = (
            gaze_fr_xyz[:, 1] + gaze_vector_start_point_fr_xyz[:, 1]
        )
        gaze_laser_fr_xyz[:, 2] = (
            gaze_fr_xyz[:, 2] + gaze_vector_start_point_fr_xyz[:, 2]
        )

        return gaze_laser_fr_xyz
