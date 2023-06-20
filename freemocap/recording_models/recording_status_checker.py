from pathlib import Path
from typing import Dict, Union

import numpy as np

from freemocap.recording_models.recording_info_model import RecordingInfoModel, logger
from freemocap.tests.test_image_tracking_data_shape import test_image_tracking_data_shape
from freemocap.tests.test_mediapipe_skeleton_data_shape import test_mediapipe_skeleton_data_shape
from freemocap.tests.test_synchronized_video_frame_counts import test_synchronized_video_frame_counts
from freemocap.tests.test_total_body_center_of_mass_data_shape import test_total_body_center_of_mass_data_shape


class RecordingFolderStatusChecker:
    def __init__(self, recording_info_model: RecordingInfoModel):

        self.recording_info_model = recording_info_model

    @property
    def status_check(self) -> Dict[str, Union[bool, str, float]]:
        return {
            'synchronized_videos_status_check': self.check_synchronized_videos_status(),
            'data2d_status_check': self.check_data2d_status(),
            'data3d_status_check': self.check_data3d_status(),
            'center_of_mass_data_status_check': self.check_center_of_mass_data_status(),
            'blender_file_status_check': self.check_blender_file_status(),
            'video_and_camera_info': {
                'number_of_synchronized_videos': self.get_number_of_mp4s_in_synched_videos_directory(),
                'number_of_frames_in_videos': self.get_number_of_frames_in_videos(),
                # 'camera_rotation_and_translation': self.get_camera_rotation_and_translation_from_calibration_toml()
            }
        }

    def check_synchronized_videos_status(self) -> bool:
        try:
            test_synchronized_video_frame_counts(self.recording_info_model.synchronized_videos_folder_path)
            return True
        except AssertionError:
            return False

    def check_data2d_status(self) -> bool:

        try:
            test_image_tracking_data_shape(
                synchronized_video_folder_path=self.recording_info_model.synchronized_videos_folder_path,
                image_tracking_data_file_path=self.recording_info_model.mediapipe_2d_data_npy_file_path,
            )

            return True
        except AssertionError as e:
            return False

    def check_data3d_status(self) -> bool:
        try:
            test_mediapipe_skeleton_data_shape(
                synchronized_video_folder_path=self.recording_info_model.synchronized_videos_folder_path,
                raw_skeleton_npy_file_path=self.recording_info_model.mediapipe_3d_data_npy_file_path,
                reprojection_error_file_path=self.recording_info_model.mediapipe_reprojection_error_data_npy_file_path,
            )
            return True
        except AssertionError as e:

            return False

    def check_center_of_mass_data_status(self) -> bool:
        try:
            test_total_body_center_of_mass_data_shape(
                synchronized_video_folder_path=self.recording_info_model.synchronized_videos_folder_path,
                total_body_center_of_mass_file_path=self.recording_info_model.total_body_center_of_mass_npy_file_path,
            )
            return True
        except AssertionError as e:
            return False

    def check_blender_file_status(self) -> bool:
        return Path(self.recording_info_model.blender_file_path).is_file()

    def check_calibration_toml_status(self) -> bool:
        return Path(self.recording_info_model.calibration_toml_path).is_file()

    def get_number_of_mp4s_in_synched_videos_directory(self) -> float:
        synchronized_directory_path = Path(self.recording_info_model.synchronized_videos_folder_path)
        video_count = 0.0

        if not synchronized_directory_path.exists():
            return video_count

        for file in synchronized_directory_path.iterdir():
            if file.is_file() and file.suffix.lower() == '.mp4':
                video_count += 1

        logger.info(f"Number of `.mp4`'s in {self.recording_info_model.synchronized_videos_folder_path}: {video_count}")
        return video_count

    def get_number_of_frames_in_videos(self):
        timestamps_directory_path = Path(self.recording_info_model.synchronized_videos_folder_path) / "timestamps"

        if not timestamps_directory_path.exists():
            return "No 'timestamps' directory found"

        if timestamps_directory_path.exists() :
            frame_counts = {}

            for npy_file in timestamps_directory_path.iterdir():
                if npy_file.is_file() and npy_file.suffix.lower() == '.npy':
                    video_npy = np.load(str(npy_file))
                    frame_counts[npy_file.name] = str(len(video_npy)-1)

            return frame_counts
