import logging
from pathlib import Path
from typing import Union
import numpy as np
from rich import inspect
from jon_scratch.pupil_calibration_pipeline.data_classes.freemocap_session_data_class import FreemocapSessionDataClass
from jon_scratch.pupil_calibration_pipeline.head_rotation_calculator import HeadRotationCalculator
from jon_scratch.pupil_calibration_pipeline.pupil_freemocap_synchronizer import PupilFreemocapSynchronizer
from jon_scratch.pupil_calibration_pipeline.qt_gl_laser_skeleton_visualizer import QtGlLaserSkeletonVisualizer
from jon_scratch.pupil_calibration_pipeline.session_data_loader import SessionDataLoader
from jon_scratch.pupil_calibration_pipeline.vor_calibrator import VorCalibrator

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PupilFreemocapCalibrationPipelineOrchestrator:
    session_data_loader: SessionDataLoader = None
    raw_session_data = FreemocapSessionDataClass()
    synchronized_session_data: FreemocapSessionDataClass = None
    laser_skeleton_visualizer = QtGlLaserSkeletonVisualizer()
    vor_frame_start: int = None,
    vor_frame_end: int = None

    def __init__(self, session_path: Union[Path, str], debug: bool = False, vor_frame_start: int = None, vor_frame_end: int = None):
        logger.info(f'initializing pupil-freemocap calibration pipeline orchestrator for session: {session_path}')
        self.session_path = session_path
        self.session_id = self.session_path.stem
        self.raw_session_data.session_id = self.session_id
        self.session_data_loader = SessionDataLoader(self.session_path)
        self.debug = debug

        if vor_frame_start is not None:
            self.vor_frame_start = vor_frame_start
        if vor_frame_end is not None:
            self.vor_frame_end = vor_frame_end

    def run(self):
        logger.info(f'loading session data from {self.session_data_loader.session_path}')

        ####
        # load raw freemocap data
        ####
        self.raw_session_data.timestamps = self.session_data_loader.load_freemocap_unix_timestamps()
        logger.info(
            f'self.raw_session_data.freemocap_timestamps.shape: {self.raw_session_data.timestamps.shape}')

        self.raw_session_data.mediapipe_skel_fr_mar_dim = self.session_data_loader.load_mediapipe_data()
        logger.info(
            f'self.raw_session_data.mediapipe_skel_fr_mar_dim.shape: {self.raw_session_data.mediapipe_skel_fr_mar_dim.shape}')

        ####
        # Calculate Head Rotation matrix for each frame (gaze data will be rotated by head_rot, then calibrated_offset_rot)
        ####
        head_rotation_calculator = HeadRotationCalculator(self.raw_session_data.mediapipe_skel_fr_mar_dim)
        head_rotation_matricies = head_rotation_calculator.calculate_head_rotation_matricies(debug=True)
        self.unrotated_right_gaze_laser_fr_xyz  = head_rotation_calculator.create_unrotated_gaze_laser(debug=True, eye='right')
        self.unrotated_left_gaze_laser_fr_xyz = head_rotation_calculator.create_unrotated_gaze_laser(debug=True, eye='left')

        self.raw_session_data.head_rotation_matricies = head_rotation_matricies
        self.save_head_rotation_matricies()
        logger.info(
            f'len(self.raw_session_data.head_rotation_matricies): {len(self.raw_session_data.head_rotation_matricies)}')

        ####
        # load pupil data
        ####
        pupil_data_handler = self.session_data_loader.load_pupil_data()
        self.raw_session_data.right_eye_data = pupil_data_handler.get_eye_data('right')
        self.raw_session_data.left_eye_data = pupil_data_handler.get_eye_data('left')

        ####
        # Synchronize pupil data with freemocap data - results in self.synchronized_session_data (each stream has exactly the same number of frames)
        ####
        self.synchronized_session_data = PupilFreemocapSynchronizer(self.raw_session_data).synchronize(debug=False, vor_frame_start=self.vor_frame_start, vor_frame_end=self.vor_frame_end)
        logger.info('synchronization complete - I should add a test to make sure everything has the same number of frames')

        ####
        # Perform Vestibular-Ocular-Reflex based calibration (see methods from (Matthis et al, 2018 and 2022) for deetos)
        ####
        vor_calibrator = VorCalibrator(self.synchronized_session_data, vor_start_frame=self.vor_frame_start, vor_end_frame=self.vor_frame_end)
        fixation_point_fr_xyz = self.synchronized_session_data.mediapipe_skel_fr_mar_dim[self.vor_frame_start:self.vor_frame_end, :, :3]
        vor_calibrator.calibrate(fixation_point_fr_xyz)

    ############################################
    ############################################
    ### helper methods
    ############################################
    ###########################################
    def save_head_rotation_matricies(self):
        save_path = self.session_path / 'DataArrays' / 'mediaPipeSkel_3d_head_rotation_matricies_fr_row_col.npy'
        logger.info(f'saving head rotation matricies to: {save_path}')
        np.save(str(save_path), self.raw_session_data.head_rotation_matricies)


if __name__ == '__main__':
    session_id = 'sesh_2022-02-15_11_54_28_pupil_maybe'
    data_path = Path('C:/Users/jonma/Dropbox/FreeMoCapProject/FreeMocap_Data/')
    this_session_path = data_path / session_id

    vor_frame_start_in = 1200
    vor_frame_end_in = 1500

    orchestrator = PupilFreemocapCalibrationPipelineOrchestrator(this_session_path, vor_frame_start=vor_frame_start_in,
                                                                 vor_frame_end=vor_frame_end_in)
    orchestrator.run()
    print('done')
