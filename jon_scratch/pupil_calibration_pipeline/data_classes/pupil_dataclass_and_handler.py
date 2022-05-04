from dataclasses import dataclass
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd


@dataclass
class PupilData:
    def __init__(self,
                 timestamps=None,
                 theta=None,
                 phi=None,
                 pupil_center_normal_x=None,
                 pupil_center_normal_y=None,
                 pupil_center_normal_z=None,
                 eye_d=None,
                 method=None):
        self.timestamps = timestamps
        self.theta = theta
        self.phi = phi
        self.pupil_center_normal_x = pupil_center_normal_x
        self.pupil_center_normal_y = pupil_center_normal_y
        self.pupil_center_normal_z = pupil_center_normal_z
        self.eye_d = eye_d
        self.method = method


class PupilDataHandler:
    """
    Class for handling data from Pupil Labs eye tracker
    """

    def __init__(self, pupil_dataframe: pd.DataFrame = None):
        if pupil_dataframe is not None:
            self.load_from_dataframe(pupil_dataframe)

    def load_from_file(self, file_path: Union[str, Path]):
        pupil_dataframe = pd.read_csv(file_path)
        self.load_from_dataframe(pupil_dataframe)

    def load_from_dataframe(self, pupil_dataframe: pd.DataFrame):
        pupil_dataframe = pupil_dataframe

        # resituate pupil data so that the pupil normal direction is situated on the origin (instead of the arbitrary eye-camera-based eyeball sphere center)
        # ... I think... I need to check this. Their docs are a bit unclear about the origin of the pupil normal direction.
        # pupil_center_normal_x = np.array(pupil_dataframe['sphere_center_x']) - np.array(pupil_dataframe['circle_3d_normal_x'])
        # pupil_center_normal_y = np.array(pupil_dataframe['sphere_center_y']) - np.array(pupil_dataframe['circle_3d_normal_y'])
        # pupil_center_normal_z = np.array(pupil_dataframe['sphere_center_z']) - np.array(pupil_dataframe['circle_3d_normal_z'])
        pupil_center_normal_x = np.array(pupil_dataframe['circle_3d_normal_x'])
        pupil_center_normal_y = np.array(pupil_dataframe['circle_3d_normal_y'])
        pupil_center_normal_z = np.array(pupil_dataframe['circle_3d_normal_z'])

        self.pupil_data = PupilData(timestamps=np.array(pupil_dataframe['pupil_timestamp']),
                                    theta=np.array(pupil_dataframe['theta']),
                                    phi=np.array(pupil_dataframe['phi']),
                                    pupil_center_normal_x=pupil_center_normal_x,
                                    pupil_center_normal_y=pupil_center_normal_y,
                                    pupil_center_normal_z=pupil_center_normal_z,
                                    eye_d=pupil_dataframe['eye_id'],
                                    method=pupil_dataframe['method'])

    def convert_to_unix_timestamps(self, pupil_recording_info_json: dict):
        self.pupil_data.timestamps = self.pupil_data.timestamps - pupil_recording_info_json['start_time_synced_s'] + \
                                     pupil_recording_info_json[
                                         'start_time_system_s']

    def get_eye_data(self, this_eye_d: int):
        """
        get data for the right eye

        pull out data according to `eye_d` (right_eye == 0, left_eye==1) and tracking method (because pupil interleaves 2d and 3d data)
        """
        this_eye_logical_indicies = np.logical_and(self.pupil_data.eye_d == this_eye_d,
                                                   self.pupil_data.method != '2d c++')
        return PupilData(
            timestamps=self.pupil_data.timestamps[this_eye_logical_indicies],
            theta=self.pupil_data.theta[this_eye_logical_indicies],
            phi=self.pupil_data.phi[this_eye_logical_indicies],
            pupil_center_normal_x=self.pupil_data.pupil_center_normal_x[this_eye_logical_indicies],
            pupil_center_normal_y=self.pupil_data.pupil_center_normal_y[this_eye_logical_indicies],
            pupil_center_normal_z=self.pupil_data.pupil_center_normal_z[this_eye_logical_indicies],
        )
