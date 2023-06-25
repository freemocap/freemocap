import json
import logging
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.mediapipe_skeleton_names_and_connections import \
    mediapipe_names_and_connections_dict
from freemocap.core_processes.post_process_skeleton_data.gap_fill_filter_and_origin_align_skeleton_data import \
    BODY_SEGMENT_NAMES
from freemocap.data_saver.data_models import FramePacket, SkeletonData, FrameData
from freemocap.system.paths_and_filenames.file_and_folder_names import MEDIAPIPE_BODY_3D_DATAFRAME_CSV_FILE_NAME, \
    MEDIAPIPE_RIGHT_HAND_3D_DATAFRAME_CSV_FILE_NAME, MEDIAPIPE_LEFT_HAND_3D_DATAFRAME_CSV_FILE_NAME, \
    MEDIAPIPE_FACE_3D_DATAFRAME_CSV_FILE_NAME
from freemocap.system.paths_and_filenames.path_getters import get_output_data_folder_path, \
    get_total_body_center_of_mass_file_path, get_segment_center_of_mass_file_path, get_full_npy_file_path, \
    get_timestamps_directory

logger = logging.getLogger(__name__)

from typing import Any, Dict


class DataSaver:

    def __init__(self,
                 recording_folder_path: Union[Path, str],
                 include_hands: bool = True,
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

        self._data_loader = DataLoader(recording_folder_path=self.recording_folder_path,
                                        include_hands=include_hands,
                                        include_face=include_face)

        self.recording_data_by_frame_number = None
        self.number_of_frames = None

    def save_all(self) -> Dict[int, Dict]:
        """
        Load all data, validate it, and create the recording_data_by_frame_number dictionary.

        Returns:
            Dict[int, Dict]: a dictionary containing the processed data, indexed by frame number.
        """

        self._get_data_by_frame_number()

        self.save_to_json()
        self.save_to_csv()
        self.save_to_npy()

    def _get_data_by_frame_number(self):
        self.recording_data_by_frame_number = {}
        for frame_number in range(len(self._data_loader.body_dataframe)):
            self.recording_data_by_frame_number[frame_number] = self._data_loader.load_frame_data(frame_number)

    def save_to_json(self, save_path:Union[str, Path]=None):
        dict_to_save = {}
        dict_to_save['data_by_frame'] = self.recording_data_by_frame_number
        dict_to_save['info'] = self._get_info_dict()

        if save_path is None:
            save_path = self.recording_folder_path / f"{self._recording_name}_by_frame.json"

        logger.info(f"Saving recording data to {save_path}")
        with open(save_path, 'w') as file:
            json.dump(dict_to_save, file, indent=4)

    def save_to_csv(self, save_path:Union[str, Path]=None):
        data_for_dataframe = []

        for frame_data in self.recording_data_by_frame_number.values():
            data_for_dataframe.append(self._generate_frame_data_row(frame_data))

        # Create DataFrame and save to csv
        df = pd.DataFrame(data_for_dataframe)

        if save_path is None:
            save_path = self.recording_folder_path / f"{self._recording_name}_by_trajectory.csv"

        df.to_csv(save_path, index=False)
        logger.info(f"Saved recording data to {save_path}")

    def save_to_npy(self, save_path:Union[str, Path]=None):
        if save_path is None:
            save_path = self.recording_folder_path / f"{self._recording_name}_fr_id_xyz.npy"
        np.save(save_path, self.data_fr_id_xyz)

    def _generate_frame_data_row(self, frame_data: Dict[str, Any]) -> Dict:
        """
        Generate a data row for a given frame number.
        """
        frame_data_row = {}

        body_parts = list(frame_data.keys())

        # put center of mass first for clandestine biomechical education porpoises
        com_index = body_parts.index('center_of_mass')
        com_name = body_parts.pop(com_index)
        body_parts.insert(0, com_name)

        # Flatten each frame's dictionary
        for body_part_key, body_part_dict in frame_data.items():
            if body_part_key == "center_of_mass":
                frame_data_row.update(self._process_center_of_mass_data(body_part_dict))
            elif body_part_key == "body":
                frame_data_row.update(self._process_body_data(body_part_dict))
            elif body_part_key == "hands":
                frame_data_row.update(self._process_hand_data(body_part_dict))
            elif body_part_key == "face":
                frame_data_row.update(self._process_face_data(body_part_dict))
            else:
                raise ValueError(f"Unknown body part: {body_part_key}")

        return frame_data_row

    def _get_info_dict(self):
        return {'segment_lengths': self.segment_lengths,
                'names_and_connections': self.names_and_connections}

class DataLoader:
    def __init__(self,
                 recording_folder_path: Union[str, Path],
                 include_hands: bool = True,
                 include_face: bool = True,):

        self._recording_folder_path = Path(recording_folder_path)
        self.include_hands = include_hands
        self.include_face = include_face

        self._recording_name = self._recording_folder_path.name
        self._output_folder_path = Path(get_output_data_folder_path(self._recording_folder_path))

        self._load_data()
        self._data_formatter = DataFormatter(data_loader=self)

    def _load_data(self):
        self._load_timestamps()
        self._load_data_frames()
        self._load_full_npy_data()
        self._load_center_of_mass_data()
        self._load_segment_lengths()
        self._load_names_and_connections()
        self._validate_data()

    def _load_data_frames(self):
        self.body_dataframe = self._load_dataframe(MEDIAPIPE_BODY_3D_DATAFRAME_CSV_FILE_NAME)
        self.number_of_frames = len(self.body_dataframe)
        if self.include_hands:
            self.right_hand_dataframe = self._load_dataframe(MEDIAPIPE_RIGHT_HAND_3D_DATAFRAME_CSV_FILE_NAME)
            self.left_hand_dataframe = self._load_dataframe(MEDIAPIPE_LEFT_HAND_3D_DATAFRAME_CSV_FILE_NAME)
        if self.include_face:
            self.face_dataframe = self._load_dataframe(MEDIAPIPE_FACE_3D_DATAFRAME_CSV_FILE_NAME)

    def _load_dataframe(self, filename):
        return pd.read_csv(self._output_folder_path / filename)

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


    def _load_timestamps(self):
        timestamps_directory = get_timestamps_directory(recording_directory=self._recording_folder_path)
        if timestamps_directory is None:
            logger.warning("No timestamps directory found. Skipping timestamps loading.")
            return

        timestamps_by_camera = {}
        for timestamps_npy in Path(timestamps_directory).glob("*.npy"):
            camera_name = timestamps_npy.stem
            timestamps_by_camera[camera_name] = np.load(timestamps_npy)

        self._timestamps_by_camera = timestamps_by_camera
        timestamps = [timestamps for timestamps in timestamps_by_camera.values()]
        self._timestamps_mean_per_frame = np.nanmean(np.asarray(timestamps), axis=0)

    def _load_center_of_mass_data(self):
        """
        Load additional data like center of mass and segment lengths.
        """
        self.center_of_mass_xyz = np.load(
            get_total_body_center_of_mass_file_path(output_data_folder=self._output_folder_path))
        self.segment_center_of_mass_segment_xyz = np.load(
            get_segment_center_of_mass_file_path(output_data_folder=self._output_folder_path))

    def _load_full_npy_data(self):
        self.data_fr_id_xyz = get_full_npy_file_path(output_data_folder=self._output_folder_path)
    def _load_names_and_connections(self):
        with open(self._output_folder_path / "mediapipe_names_and_connections_dict.json", 'r') as file:
            self.names_and_connections = json.loads(file.read())

    def _load_segment_lengths(self):
        with open(self._output_folder_path / "mediapipe_skeleton_segment_lengths.json", 'r') as file:
            self.segment_lengths = json.loads(file.read())

    def load_frame_data(self, frame_number:int):
        frame_data = FrameData()
        schema = SkeletonSchema(names_and_connections=self.names_and_connections)









class DataFormatter:
    def __init__(self, data_loader: DataLoader):
        self.data_loader = data_loader


    def _format_frame_data(self, frame_number: int):
        """
        Process data for a given frame number.
        """
        body_data = self._data_loader.body_data[frame_number]

        hands = None
        face = None
        if self.data_loader.include_hands:
            hands = {}
            hands["right"] = self._process_dataframe(
                data_frame=self.data_loader.right_hand_dataframe.iloc[frame_number])
            hands["right"] = self._process_dataframe(
                data_frame=self.data_loader.right_hand_dataframe.iloc[frame_number])

        if self.data_loader.include_face:
            face = self._process_dataframe(self.data_loader.face_dataframe.iloc[frame_number])

        center_of_mass = self._get_center_of_mass_data(frame_number)



        return SkeletonData(body=body_data,
                            hands=hands,
                            face=face,
                            center_of_mass=center_of_mass)

    def _get_center_of_mass_data(self, frame_number: int):
        """
        Calculate the center of mass for a given frame number.
        """

        full_body_com = {'full_body_com': {f"{dimension}": value for dimension, value in
                                           zip(["x", "y", "z"], self.center_of_mass_xyz[frame_number, :])}}

        segment_coms = {}
        for segment_number, segment_name in enumerate(BODY_SEGMENT_NAMES):
            segment_coms[segment_name] = {f"{dimension}": value for dimension, value in
                                          zip(["x", "y", "z"],
                                              self.segment_center_of_mass_segment_xyz[frame_number, segment_number, :])}

        return {"full_body_com": full_body_com,
                "segment_coms": segment_coms}

    def _process_dataframe(self, data_frame, hand_side: str = None) -> Dict[str, Any]:
        """
        Process a single row from a dataframe and add it to the recording_data_by_frame_number dictionary.

        Args:
            data_frame (DataFrame): the dataframe to process.
            hand_side (str, optional): if body_part is 'hands', this specifies which hand ('right' or 'left').
        """
        frame_data = {}
        column_names = list(data_frame.index)
        for column_name in column_names:
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
                frame_data[hand_side] = {}

            value = data_frame[column_name]
            if pd.isna(value):  # Check if value is NaN
                value = None  # Replace NaN with None which is valid in JSON

            frame_data.setdefault(point_name, {})[dimension] = value

        return frame_data

    def _process_center_of_mass_data(self, frame_data_dict: Dict[str, Any]) -> Dict:
        """
        Process center of mass data for the CSV export.
        """
        frame_data_row = {}
        for sub_dict_key, sub_dict in frame_data_dict.items():
            if sub_dict_key == "full_body_com":
                for dimension, value in sub_dict[sub_dict_key].items():
                    frame_data_row[f"center_of_mass.{sub_dict_key}.{dimension}"] = value
            elif sub_dict_key == "segment_coms":
                for segment_name in sub_dict.keys():
                    for dimension, value in sub_dict[segment_name].items():
                        frame_data_row[f"center_of_mass.{sub_dict_key}.{segment_name}.{dimension}"] = value
        return frame_data_row

    def _process_hand_data(self, body_part_dict: Dict) -> Dict:
        """
        Process hand data for the CSV export.
        """
        frame_data_row = {}
        for hand_side in body_part_dict.keys():
            for point_name in body_part_dict[hand_side].keys():
                for dimension, value in body_part_dict[hand_side][point_name].items():
                    frame_data_row[f"hands.{hand_side}.{point_name}.{dimension}"] = value
        return frame_data_row

    def _process_face_data(self, face_data_dict: Dict) -> Dict:
        """
        Process face parts' data for the CSV export.
        """
        frame_data_row = {}
        for point_name in face_data_dict.keys():
            for dimension, value in face_data_dict[point_name].items():
                frame_data_row[f"face.{point_name}.{dimension}"] = value
        return frame_data_row

    def _process_body_data(self, body_data_dict: Dict) -> Dict:
        """
        Process body parts' data for the CSV export.
        """
        frame_data_row = {}
        for point_name in body_data_dict.keys():
            for dimension, value in body_data_dict[point_name].items():
                frame_data_row[f"body.{point_name}.{dimension}"] = value
        return frame_data_row



if __name__ == '__main__':
    # recording_data_saver = DataSaver(recording_folder_path=get_sample_data_path())
    recording_data_saver = DataSaver(recording_folder_path=r"C:\Users\jonma\freemocap_data\recording_sessions\session_2023-04-14_15_29_45\recording_15_47_37_gmt-4")
    recording_data_by_frame_number = recording_data_saver.save_all()
