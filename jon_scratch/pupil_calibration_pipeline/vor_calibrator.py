import logging

import numpy as np
from matplotlib import pyplot as plt
import matplotlib

from jon_scratch.pupil_calibration_pipeline.data_classes.freemocap_session_data_class import FreemocapSessionDataClass

matplotlib.use('qt5agg')
logger = logging.getLogger(__name__)


class VorCalibrator:
    """
    Calibrate synchronized eye data from a Pupil Labs eye tracker with FreeMoCap skeleton
    see methods sections of (Matthis, Yates, and Hayhoe, Current Biology, 2018) and (Matthis, Muller, Bonnen, Hayehoe, PLoS Computation Biology 2022) for details
    """

    def __init__(self, session_data: FreemocapSessionDataClass, vor_start_frame: int = None, vor_end_frame: int = None):
        self.session_data = session_data
        if vor_start_frame is not None:
            if vor_end_frame is None:
                raise ValueError("Must specify vor_end_frame if vor_start_frame is specified")
            self.clip_out_vor_frames(vor_start_frame, vor_end_frame)

    def calibrate(self, fixation_point_fr_xyz: np.ndarray) -> FreemocapSessionDataClass:

        if not fixation_point_fr_xyz.shape[1] == 3:
            raise Exception("fixation_point_fr_xyz must be a numpy array with 3 columns")
        if not fixation_point_fr_xyz.shape[0] == self.mediapipe_skel_fr_mar_dim.shape[0]:
            raise Exception("fixation_point_xyz must have precisely the same number of rows as the skeleton/gaze data")

        self.calculate_optimal_rotational_offset()
        self.create_skeleton_gaze_lasers()
        return self.session_data

    def clip_out_vor_frames(self, vor_start_frame, vor_end_frame):
        self.mediapipe_skel_fr_mar_dim = self.session_data.mediapipe_skel_fr_mar_dim[vor_start_frame:vor_end_frame,:,:]
        self.head_rotation_matricies = self.session_data.head_rotation_data.rotation_matricies[vor_start_frame:vor_end_frame]

        self.right_eye_theta = self.session_data.right_eye_data.theta[vor_start_frame:vor_end_frame]
        self.right_eye_phi = self.session_data.right_eye_data.phi[vor_start_frame:vor_end_frame]

        self.left_eye_phi = self.session_data.left_eye_data.phi[vor_start_frame:vor_end_frame]
        self.left_eye_theta = self.session_data.left_eye_data.theta[vor_start_frame:vor_end_frame]


    def calculate_optimal_rotational_offset(self):
        pass

    def create_skeleton_gaze_lasers(self):
        pass
