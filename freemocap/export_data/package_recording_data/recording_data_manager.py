import json
import logging
from pathlib import Path
from typing import Dict, Union

import numpy as np
import pandas as pd

from freemocap.core_processes.post_process_skeleton_data.gap_fill_filter_and_origin_align_skeleton_data import \
    BODY_SEGMENT_NAMES
from freemocap.system.paths_and_filenames.path_getters import get_output_data_folder_path, \
    get_total_body_center_of_mass_file_path, get_segment_center_of_mass_file_path
from freemocap.utilities.download_sample_data import get_sample_data_path

logger = logging.getLogger(__name__)


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
        self.recording_folder_path = Path(recording_folder_path)
        self._recording_name = self.recording_folder_path.name
        self.include_hands = include_hands
        self.include_face = include_face
        self.output_folder_path = Path(get_output_data_folder_path(self.recording_folder_path))
        self.recording_data_by_frame_number = {}

        self.number_of_frames = None
        self.body_dataframe = None
        self.right_hand_dataframe = None
        self.left_hand_dataframe = None
        self.face_dataframe = None
        self.center_of_mass_xyz = None
        self.segment_center_of_mass_xyz = None

        self._load_data()

    def run(self, save_to_json: bool = True, save_to_csv: bool = True) -> Dict[int, Dict]:
        """
        Load all data, validate it, and create the recording_data_by_frame_number dictionary.

        Returns:
            Dict[int, Dict]: a dictionary containing the processed data, indexed by frame number.
        """
        self._load_data()
        self._create_recording_data_by_frame_number()
        if save_to_json:
            self._save_to_json()
        if save_to_csv:
            self._save_to_csv()

        return self.recording_data_by_frame_number

    def _load_data(self):
        self._load_data_frames()
        self._load_center_of_mass_data()
        self._load_segment_lengths()
        self._load_names_and_connections()
        self._validate_data()

    def _load_data_frames(self):
        self.body_dataframe = self._load_dataframe("mediapipe_body_3d_xyz.csv")
        self.number_of_frames = len(self.body_dataframe)
        if self.include_hands:
            self.right_hand_dataframe = self._load_dataframe("mediapipe_right_hand_3d_xyz.csv")
            self.left_hand_dataframe = self._load_dataframe("mediapipe_left_hand_3d_xyz.csv")
        if self.include_face:
            self.face_dataframe = self._load_dataframe("mediapipe_face_3d_xyz.csv")



    def _load_dataframe(self, filename):
        return pd.read_csv(self.output_folder_path / filename)

    def _validate_data(self):
        self._validate_dataframe(self.right_hand_dataframe, 'right hand')
        self._validate_dataframe(self.left_hand_dataframe, 'left hand')
        self._validate_dataframe(self.face_dataframe, 'face')
        self._validate_numpy_array(self.center_of_mass_xyz, 'center of mass')
        self._validate_numpy_array(self.segment_center_of_mass_segment_xyz, 'segment center of mass')

    def _validate_dataframe(self, df, df_name):
        if df is not None and len(df) != self.number_of_frames:
            raise ValueError(
                f"The number of frames in the {df_name} dataframe is different from the number of frames in the body dataframe.")

    def _validate_numpy_array(self, np_array, np_array_name):
        if np_array is not None and np_array.shape[0] != self.number_of_frames:
            raise ValueError(
                f"The number of frames in the {np_array_name} data is different from the number of frames in the body dataframe.")

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
                "center_of_mass": {"full_body": {}, "segments": {}},
                "body": {},
                "hands": {"right": {}, "left": {}},
                "face": {},
            }
            self._process_dataframe(self.body_dataframe.iloc[frame_number], "body", frame_number)
            if self.include_hands:
                self._process_dataframe(self.right_hand_dataframe.iloc[frame_number], "hands", frame_number, "right")
                self._process_dataframe(self.left_hand_dataframe.iloc[frame_number], "hands", frame_number, "left")
            if self.include_face:
                self._process_dataframe(self.face_dataframe.iloc[frame_number], "face", frame_number)

            self.recording_data_by_frame_number[frame_number]['center_of_mass']['full_body'] = {f"{dimension}": value
                                                                                                for
                                                                                                dimension, value in
                                                                                                zip(["x", "y", "z"],
                                                                                                    self.center_of_mass_xyz[
                                                                                                    frame_number, :])}

            for segment_number, segment_name in enumerate(BODY_SEGMENT_NAMES):
                segment_xyz = self.segment_center_of_mass_segment_xyz[frame_number, segment_number, :]
                self.recording_data_by_frame_number[frame_number]['center_of_mass']['segments'][segment_name] = {
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
                # remove redundant naming from hand points (e.g. "right_hand_thumb_1" -> "thumb_1")
                split = point_name.split("_")
                if split[0] == hand_side:
                    split.pop(0)
                if split[0] == "hand":
                    split.pop(0)
                point_name = "_".join(split)

                self.recording_data_by_frame_number[frame_number][body_part][hand_side].setdefault(point_name, {})[
                    dimension] = data_frame[column_name]
            else:
                self.recording_data_by_frame_number[frame_number][body_part].setdefault(point_name, {})[dimension] = \
                    data_frame[column_name]


    def _save_to_json(self):
        json_file_path = self.recording_folder_path / f"{self._recording_name}_by_frame.json"
        logger.info(f"Saving recording data to {json_file_path}")
        with open(json_file_path, 'w') as file:
            json.dump(self.recording_data_by_frame_number, file, indent=4)

    def _save_to_csv(self):
        data_for_dataframe = []

        for frame_number in self.recording_data_by_frame_number.keys():
            if isinstance(frame_number, int):  # Skip 'segment_lengths' and 'names_and_connections' entries
                frame_data_row = {}

                body_parts = list(self.recording_data_by_frame_number[frame_number].keys())
                com_index = body_parts.index('center_of_mass')
                com_name = body_parts.pop(com_index)
                body_parts.insert(0, com_name)

                # Flatten each frame's dictionary
                for body_part_key, body_part_dict in self.recording_data_by_frame_number[frame_number].items():

                    if body_part_key == "center_of_mass":
                        for sub_dict_key, sub_dict in self.recording_data_by_frame_number[frame_number][
                            body_part_key].items():
                            if sub_dict_key == "full_body":
                                for dimension, value in sub_dict.items():
                                    frame_data_row[f"{body_part_key}.{sub_dict_key}.{dimension}"] = value
                            elif sub_dict_key == "segment":
                                for segment_name in sub_dict.keys():
                                    for dimension, value in sub_dict[segment_name].items():
                                        frame_data_row[f"{body_part_key}.{segment_name}.{dimension}"] = value
                    elif body_part_key == "hands":
                        for hand_side in body_part_dict.keys():
                            for point_name in body_part_dict[
                                hand_side].keys():
                                for dimension, value in \
                                        body_part_dict[hand_side][
                                            point_name].items():
                                    frame_data_row[f"{body_part_key}.{hand_side}.{point_name}.{dimension}"] = value
                    else:
                        for point_name in body_part_dict.keys():

                            for dimension, value in body_part_dict[
                                point_name].items():
                                frame_data_row[f"{body_part_key}.{point_name}.{dimension}"] = value

                data_for_dataframe.append(frame_data_row)

        # Create DataFrame and save to csv
        df = pd.DataFrame(data_for_dataframe)
        csv_file_path = self.recording_folder_path / f"{self._recording_name}_by_trajectory.csv"
        df.to_csv(csv_file_path, index=False)
        logger.info(f"Saved recording data to {csv_file_path}")


if __name__ == '__main__':
    recording_data_manager = RecordingDataManager(recording_folder_path=get_sample_data_path())
    recording_data_by_frame_number = recording_data_manager.run()
