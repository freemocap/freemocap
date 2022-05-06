import logging
from typing import Union, List

import numpy as np
from matplotlib import pyplot as plt
import matplotlib

from jon_scratch.pupil_calibration_pipeline.data_classes.freemocap_session_data_class import FreemocapSessionDataClass
from jon_scratch.pupil_calibration_pipeline.data_classes.pupil_dataclass_and_handler import PupilLabsDataClass
from jon_scratch.pupil_calibration_pipeline.data_classes.rotation_data_class import RotationDataClass

matplotlib.use('qt5agg')
logger = logging.getLogger(__name__)


class VorCalibrator:
    """
    Calibrate synchronized eye data from a Pupil Labs eye tracker with FreeMoCap skeleton
    see methods sections of (Matthis, Yates, and Hayhoe, Current Biology, 2018) and (Matthis, Muller, Bonnen, Hayehoe, PLoS Computation Biology 2022) for details
    """

    def __init__(self, mediapipe_skel_fr_mar_xyz: np.ndarray,
                 vor_start_frame: int = None,
                 vor_end_frame: int = None):
        self.mediapipe_skel_fr_mar_xyz = mediapipe_skel_fr_mar_xyz
        if vor_start_frame is not None:
            self.vor_start_frame = vor_start_frame
            if vor_end_frame is None:
                raise ValueError("Must specify vor_end_frame if vor_start_frame is specified")
            self.vor_end_frame = vor_end_frame

    def calibrate(self,
                  pupil_labs_eye_data: PupilLabsDataClass,
                  eye_socket_rotation_data: RotationDataClass,
                  fixation_point_fr_xyz: np.ndarray) -> np.ndarray:

        if not fixation_point_fr_xyz.shape[1] == 3:
            raise Exception("fixation_point_fr_xyz must be a numpy array with 3 columns")

        gaze_vector_start_point_fr_xyz = eye_socket_rotation_data.local_origin_fr_xyz
        gaze_unit_vector_end_point_fr_xyz = eye_socket_rotation_data.z_hat_norm_fr_xyz
        self.fixation_distance = self.get_fixation_distance(fixation_point_fr_xyz,
                                                            gaze_vector_start_point_fr_xyz[
                                                            self.vor_start_frame:self.vor_end_frame, :])

        gaze_vector_endpoint_fr_xyz = self.create_unrotated_gaze_lasers_from_eye_rotation_matrixies(
            gaze_vector_start_point_fr_xyz,
            gaze_unit_vector_end_point_fr_xyz,
            np.nanmedian(self.fixation_distance))

        # self.clip_out_vor_frames(self.vor_start_frame, self.vor_end_frame)
        # if not fixation_point_fr_xyz.shape[0] == self.mediapipe_skel_fr_mar_xyz.shape[0]:
        #     raise Exception(
        #         "fixation_point_xyz must have precisely the same number of rows as the skeleton/gaze data after clipping out the VOR data")

        return gaze_vector_endpoint_fr_xyz

    def clip_out_vor_frames(self, vor_start_frame, vor_end_frame):
        self.mediapipe_skel_fr_mar_xyz = self.session_data.mediapipe_skel_fr_mar_xyz[vor_start_frame:vor_end_frame, :,
                                         :]
        # right eye
        self.right_eyeball_center_fr_xyz = self.session_data.right_eye_socket_rotation_data.local_origin_fr_xyz[
                                           vor_start_frame:vor_end_frame, :]
        self.right_eye_rotation_matricies = self.session_data.right_eye_socket_rotation_data.rotation_matricies[
                                            vor_start_frame:vor_end_frame]
        self.right_eye_theta = self.session_data.right_eye_pupil_labs_data.theta[vor_start_frame:vor_end_frame]
        self.right_eye_phi = self.session_data.right_eye_pupil_labs_data.phi[vor_start_frame:vor_end_frame]

        # left eye
        self.left_eyeball_center_fr_xyz = self.session_data.left_eye_socket_rotation_data.local_origin_fr_xyz[
                                          vor_start_frame:vor_end_frame, :]
        self.left_eye_rotation_matricies = self.session_data.left_eye_socket_rotation_data.rotation_matricies[
                                           vor_start_frame:vor_end_frame]
        self.left_eye_phi = self.session_data.left_eye_pupil_labs_data.phi[vor_start_frame:vor_end_frame]
        self.left_eye_theta = self.session_data.left_eye_pupil_labs_data.theta[vor_start_frame:vor_end_frame]

    def calculate_optimal_rotational_offset(self):
        pass

    def get_fixation_distance(self, local_origin_fr_xyz, fixation_point_fr_xyz):
        return np.linalg.norm(local_origin_fr_xyz - fixation_point_fr_xyz, axis=1)

    def create_unrotated_gaze_lasers_from_eye_rotation_matrixies(self,
                                                                 gaze_vector_start_point_fr_xyz: np.ndarray,
                                                                 gaze_unit_vector_end_point_fr_xyz: np.ndarray,
                                                                 calbration_distance,
                                                                 ) -> np.ndarray:
        """
        Creates an unrotated gaze laser for each frame in the skeleton/gaze data. Returns a vector the same length as the calibration_distance, shooting our of the skeletons eye_sockets (as if they eyes were paralyzed).
        """
        if not gaze_vector_start_point_fr_xyz.shape == gaze_unit_vector_end_point_fr_xyz.shape:
            raise Exception("`gaze_vector_start_point_fr_xyz` and `gaze_unit_vector_end_point_fr_xyz` must have the same shape")

        #scale gaze vector so it's the same norm/length as the calibration distance
        gaze_unit_vector_end_point_fr_xyz = gaze_unit_vector_end_point_fr_xyz * calbration_distance

        #move it from an zero-centered reference frame to the eye socket reference frame
        gaze_vector_end_point_fr_xyz = gaze_unit_vector_end_point_fr_xyz + gaze_vector_start_point_fr_xyz

        return gaze_vector_end_point_fr_xyz

    def create_skeleton_gaze_lasers(self, gaze_laser_centered_on_zero_fr_xyz):

        return gaze_laser_centered_on_zero_fr_xyz
