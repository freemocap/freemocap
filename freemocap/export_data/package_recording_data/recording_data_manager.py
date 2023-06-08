import json
import logging
from pathlib import Path
from typing import Dict, Union

import numpy as np
import pandas as pd

from freemocap.core_processes.post_process_skeleton_data.gap_fill_filter_and_origin_align_skeleton_data import \
    BODY_SEGMENT_NAMES
from freemocap.system.paths_and_filenames.path_getters import get_output_data_folder_path, \
    get_total_body_center_of_mass_file_path, get_segment_center_of_mass_file_path, get_sample_data_path


logger  = logging.getLogger(__name__)
class RecordingDataManager:
    """
    Manages operations related to processing dataframes containing body, hands, and face data.
    """

    def __init__(self, recording_folder_path: Union[Path, str], include_hands: bool = True,
                 include_face: bool = True):
        """
        Initialize DataFrameManager with the given recording_folder_path.

        Args:
            recording_folder_path (Union[Path, str]): path to the folder containing the recording data.
            include_hands (bool): flag to include hands data in the processing.
            include_face (bool): flag to include face data in the processing.
        """
        self.recording_folder_path = recording_folder_path
        self._recording_name = Path(recording_folder_path).name
        self.include_hands = include_hands
        self.include_face = include_face
        self.output_folder_path = Path(get_output_data_folder_path(recording_folder_path))
        self.recording_data_by_frame_number = {}

        self.body_dataframe = None
        self.right_hand_dataframe = None
        self.left_hand_dataframe = None
        self.face_dataframe = None
        self.center_of_mass_xyz = None
        self.segment_center_of_mass_xyz = None

        self._load_data()

    def run(self, save_to_json:bool=True) -> Dict[int, Dict]:
        """
        Load all data, validate it, and create the recording_data_by_frame_number dictionary.

        Returns:
            Dict[int, Dict]: a dictionary containing the processed data, indexed by frame number.
        """
        self._load_data()
        self._create_recording_data_by_frame_number()
        if save_to_json:
            self._save_to_json()
        return self.recording_data_by_frame_number

    def _load_data(self):
        self._load_data_frames()
        self._load_center_of_mass_data()
        self._load_segment_lengths()
        self._load_names_and_connections()
        self._validate_data()

    def _load_data_frames(self):
        """
        Load body, hands, and face dataframes from csv files in the output_folder_path.
        """

        self.body_dataframe = pd.read_csv(self.output_folder_path / "mediapipe_body_3d_xyz.csv")
        self.numbers_of_frames = len(self.body_dataframe)
        if self.include_hands:
            self.right_hand_dataframe = pd.read_csv(self.output_folder_path / "mediapipe_right_hand_3d_xyz.csv")

            self.left_hand_dataframe = pd.read_csv(self.output_folder_path / "mediapipe_left_hand_3d_xyz.csv")

        if self.include_face:
            self.face_dataframe = pd.read_csv(self.output_folder_path / "mediapipe_face_3d_xyz.csv")

    def _load_center_of_mass_data(self):
        """
        Load additional data like center of mass and segment lengths.
        """
        self.center_of_mass_xyz = np.load(
            get_total_body_center_of_mass_file_path(output_data_folder=self.output_folder_path))
        self.segment_center_of_mass_segment_xyz = np.load(
            get_segment_center_of_mass_file_path(output_data_folder=self.output_folder_path))

    def _load_names_and_connections(self):
        with open(self.output_folder_path / "mediapipe_names_and_connections_dict.json", 'r') as file:
            self.names_and_connections = json.loads(file.read())

    def _load_segment_lengths(self):
        with open(self.output_folder_path / "mediapipe_skeleton_segment_lengths.json", 'r') as file:
            self.segment_lengths = json.loads(file.read())

    def _create_recording_data_by_frame_number(self):
        """
        Create a dictionary of dataframes indexed by frame number.
        """
        self.recording_data_by_frame_number['segment_lengths'] = self.segment_lengths
        self.recording_data_by_frame_number['names_and_connections'] = self.names_and_connections

        for frame_number in range(len(self.body_dataframe)):
            self.recording_data_by_frame_number[frame_number] = {
                "body": {},
                "hands": {"right": {}, "left": {}},
                "face": {},
                "total_body_center_of_mass": {},
                "segment_centers_of_mass": {},
            }
            self._process_dataframe(self.body_dataframe.iloc[frame_number], "body", frame_number)
            if self.include_hands:
                self._process_dataframe(self.right_hand_dataframe.iloc[frame_number], "hands", frame_number, "right")
                self._process_dataframe(self.left_hand_dataframe.iloc[frame_number], "hands", frame_number, "left")
            if self.include_face:
                self._process_dataframe(self.face_dataframe.iloc[frame_number], "face", frame_number)

            self.recording_data_by_frame_number[frame_number]['total_body_center_of_mass'] = {f"{dimension}": value for
                                                                                   dimension, value in
                                                                                   zip(["x", "y", "z"],
                                                                                       self.center_of_mass_xyz[
                                                                                       frame_number, :])}

            for segment_number, segment_name in enumerate(BODY_SEGMENT_NAMES):
                segment_xyz = self.segment_center_of_mass_segment_xyz[frame_number, segment_number, :]
                self.recording_data_by_frame_number[frame_number]['segment_centers_of_mass'][segment_name] = {
                    f"{dimension}": value for dimension, value in zip(["x", "y", "z"], list(segment_xyz))}


    def _process_dataframe(self, data_frame, body_part: str, frame_number: int, hand_side: str = None):
        """
        Process a single row from a dataframe and add it to the recording_data_by_frame_number dictionary.

        Args:
            data_frame (DataFrame): the dataframe to process.
            body_part (str): the body part this dataframe pertains to (body, hands, or face).
            frame_number (int): the frame number this data pertains to.
            hand_side (str, optional): if body_part is 'hands', this specifies which hand ('right' or 'left').
        """
        for column_name in data_frame.index:
            point_name = column_name[:-2]  # e.g. "nose" or "left_knee" or whatever
            dimension = column_name[-1]  # e.g. "x" or "y" or "z"

            if hand_side:
                self.recording_data_by_frame_number[frame_number][body_part][hand_side].setdefault(point_name, {})[
                    dimension] = data_frame[column_name]
            else:
                self.recording_data_by_frame_number[frame_number][body_part].setdefault(point_name, {})[dimension] = \
                    data_frame[column_name]

    def _validate_data(self):
        if self.right_hand_dataframe is not None:
            if len(self.right_hand_dataframe) != self.numbers_of_frames:
                raise ValueError(
                    "The number of frames in the right hand dataframe is different from the number of frames in the body dataframe.")
        if self.left_hand_dataframe is not None:
            if len(self.left_hand_dataframe) != self.numbers_of_frames:
                raise ValueError(
                    "The number of frames in the left hand dataframe is different from the number of frames in the body dataframe.")
        if self.face_dataframe is not None:
            if len(self.face_dataframe) != self.numbers_of_frames:
                raise ValueError(
                    "The number of frames in the face dataframe is different from the number of frames in the body dataframe.")
        if self.center_of_mass_xyz is not None:
            if self.center_of_mass_xyz.shape[0] != self.numbers_of_frames:
                raise ValueError(
                    "The number of frames in the center of mass data is different from the number of frames in the body dataframe.")
        if self.segment_center_of_mass_segment_xyz is not None:
            if self.segment_center_of_mass_segment_xyz.shape[0] != self.numbers_of_frames:
                raise ValueError(
                    "The number of frames in the segment center of mass data is different from the number of frames in the body dataframe.")

    def _save_to_json(self):
        json_file_path = self.output_folder_path / f"all_data_by_frame_number.json"
        logger.info(f"Saving recording data to {json_file_path}")
        with open(json_file_path, 'w') as file:
            json.dump(self.recording_data_by_frame_number, file, indent=4)


if __name__ == '__main__':
    from pprint import pprint
    recording_data_manager = RecordingDataManager(recording_folder_path=get_sample_data_path())
    recording_data_by_frame_number = recording_data_manager.run()
    pprint(recording_data_by_frame_number)
