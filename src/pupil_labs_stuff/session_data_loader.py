import json
import logging
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from src.pupil_labs_stuff.data_classes.pupil_dataclass_and_handler import PupilDataHandler

logger = logging.getLogger(__name__)


class SessionDataLoader:
    _session_path: Path = None

    def __init__(self, session_path):

        self._session_path = Path(session_path)

    @property
    def session_path(self):
        return self._session_path

    def load_freemocap_unix_timestamps(self):
        """
        load/calculate the unix timestamps for the freemocap data (as mean of each camera's timestamp on each frame)

        """
        freemocap_unix_timestamp_path = self.session_path / "unix_synced_timestamps.csv"
        freemocap_unix_timestamps_dataframe = pd.read_csv(freemocap_unix_timestamp_path)
        each_cam_timestamps_list = []
        camera_names = [
            column_name for column_name in list(freemocap_unix_timestamps_dataframe.columns) if "Cam" in column_name
        ]

        for this_camera_name in camera_names:
            each_cam_timestamps_list.append(np.array(freemocap_unix_timestamps_dataframe[this_camera_name]))

        cameras_timestamp_array = np.stack(each_cam_timestamps_list, axis=1)
        cameras_timestamp_array[cameras_timestamp_array == -1] = np.nan  # replace -1 with nan

        freemocap_timestamps = np.nanmean(cameras_timestamp_array, axis=1)
        return freemocap_timestamps

    def load_mediapipe_data(
        self,
        session_path: Union[Path, str] = None,
        include_hands: bool = True,
        include_face: bool = False,
        move_to_origin: bool = False,
    ) -> np.ndarray:

        if session_path is not None:
            self.session_path(session_path)

        if self._session_path is None:
            raise ValueError("Session path is not specified - Can't load mediapipe data without a session path")

        mediapipe_data_path = self.session_path / "DataArrays" / "mediaPipeSkel_3d_smoothed.npy"
        logger.info(f"loading mediapipe data from {mediapipe_data_path}")
        mediapipe_fr_mar_xyz = np.load(str(mediapipe_data_path))

        if move_to_origin:
            mean_position_xyz = np.nanmedian(np.nanmedian(mediapipe_fr_mar_xyz, axis=0), axis=0)
            mediapipe_fr_mar_xyz[:, :, 0] -= mean_position_xyz[0]
            mediapipe_fr_mar_xyz[:, :, 1] -= mean_position_xyz[1]
            mediapipe_fr_mar_xyz[:, :, 2] -= mean_position_xyz[2]

        if include_face:
            return mediapipe_fr_mar_xyz  # body + hands + face

        if include_hands:
            return mediapipe_fr_mar_xyz[:, :75, :]  # body + hands, but not face

        return mediapipe_fr_mar_xyz[:, :33, :]  # just the body marker

    def load_pupil_data(self) -> PupilDataHandler:
        """
        # load in data recorded with a Pupil Labs eye tracker.
        - pupil data from `pupil_positions.csv` in the **pupil exports** folder
            - definitions in `pupil_gaze_positions_info.txt` of same folder
        - pupil start time from `info.player.json` for syncing
        """
        pupil_data_path = self.session_path / "pupil_000"
        pupil_data_exports_path = pupil_data_path / "exports" / "000"
        pupil_positions_path = pupil_data_exports_path / "pupil_positions.csv"
        pupil_recording_info_path = pupil_data_path / "info.player.json"
        freemocap_unix_timestamp_path = self.session_path / "unix_synced_timestamps.csv"

        logger.info(f"loading pupil data from {pupil_positions_path}")
        pupil_dataframe = pd.read_csv(pupil_positions_path)
        pupil_recording_info_json = json.load(open(pupil_recording_info_path))
        freemocap_unix_timestamps_dataframe = pd.read_csv(freemocap_unix_timestamp_path)

        pupil_data_handler = PupilDataHandler(pupil_dataframe)
        pupil_data_handler.convert_to_unix_timestamps(pupil_recording_info_json)

        return pupil_data_handler


if __name__ == "__main__":
    data_path = Path("C:/Users/jonma/Dropbox/FreeMoCapProject/FreeMocap_Data/")
    session_path = data_path / "sesh_2022-02-15_11_54_28_pupil_maybe"

    session_data_loader = SessionDataLoader(session_path)
    pupil_data = session_data_loader.load_pupil_data()
    print("pupil data loaded, but I don't have an easy way to print out the shape of things yet, lol")
    mediapipe_skel_fr_mar_xyz = session_data_loader.load_mediapipe_data()
    print(f"mediapipe_skel_fr_mar_xyz.shape: {mediapipe_skel_fr_mar_xyz.shape}")
