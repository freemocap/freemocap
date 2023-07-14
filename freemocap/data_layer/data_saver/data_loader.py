import json
import logging
from pathlib import Path
from typing import Union, Dict, Any

import numpy as np
import pandas as pd

from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.data_models.mediapipe_skeleton_names_and_connections import (
    mediapipe_skeleton_schema,
)
from freemocap.core_processes.post_process_skeleton_data.calculate_center_of_mass import BODY_SEGMENT_NAMES
from freemocap.data_layer.data_saver.data_models import FrameData, Timestamps, Point, SkeletonSchema
from freemocap.system.paths_and_filenames.file_and_folder_names import (
    MEDIAPIPE_BODY_3D_DATAFRAME_CSV_FILE_NAME,
    MEDIAPIPE_RIGHT_HAND_3D_DATAFRAME_CSV_FILE_NAME,
    MEDIAPIPE_LEFT_HAND_3D_DATAFRAME_CSV_FILE_NAME,
    MEDIAPIPE_FACE_3D_DATAFRAME_CSV_FILE_NAME,
)
from freemocap.system.paths_and_filenames.path_getters import (
    get_output_data_folder_path,
    get_timestamps_directory,
    get_total_body_center_of_mass_file_path,
    get_segment_center_of_mass_file_path,
    get_full_npy_file_path,
)

logger = logging.getLogger(__name__)


class DataLoader:
    def __init__(
        self,
        recording_folder_path: Union[str, Path],
        include_hands: bool = True,
        include_face: bool = True,
    ):
        self._recording_folder_path = Path(recording_folder_path)
        self.include_hands = include_hands
        self.include_face = include_face

        self._recording_name = self._recording_folder_path.name
        self._output_folder_path = Path(get_output_data_folder_path(self._recording_folder_path))

        self._load_data()

    def _load_data(self):
        self._load_timestamps()
        self._load_data_frames()
        self._load_full_npy_data()
        self._load_center_of_mass_data()
        self._load_segment_lengths()
        self._load_names_and_connections()
        self._load_skeleton_schema()
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
        self._validate_dataframe(self.right_hand_dataframe, "right hand")
        self._validate_dataframe(self.left_hand_dataframe, "left hand")
        self._validate_dataframe(self.face_dataframe, "face")
        self._validate_numpy_array(self.center_of_mass_xyz, "center of mass")
        self._validate_numpy_array(self.segment_center_of_mass_segment_xyz, "segment center of mass")

    def _validate_dataframe(self, df, df_name):
        if df is not None and len(df) != self.number_of_frames:
            raise ValueError(
                f"The number of frames in the {df_name} dataframe is different from the number of frames in the body dataframe."
            )

    def _validate_numpy_array(self, np_array, np_array_name):
        if np_array is not None and np_array.shape[0] != self.number_of_frames:
            raise ValueError(
                f"The number of frames in the {np_array_name} data is different from the number of frames in the body dataframe."
            )

    def _load_timestamps(self):
        timestamps_directory = get_timestamps_directory(recording_directory=self._recording_folder_path)
        if timestamps_directory is None:
            logger.warning("No timestamps directory found. Skipping timestamps loading.")
            return

        timestamps_by_camera = {}
        for timestamps_npy in Path(timestamps_directory).glob("*.npy"):
            camera_name = timestamps_npy.stem
            timestamps_by_camera[camera_name] = np.load(str(timestamps_npy))

        self._timestamps_by_camera = timestamps_by_camera
        timestamps = [timestamps for timestamps in timestamps_by_camera.values()]
        self._timestamps_mean_per_frame = np.nanmean(np.asarray(timestamps), axis=0)

    def _load_center_of_mass_data(self):
        """
        Load additional data like center of mass and segment lengths.
        """
        self.center_of_mass_xyz = np.load(
            get_total_body_center_of_mass_file_path(output_data_folder=self._output_folder_path)
        )
        self.segment_center_of_mass_segment_xyz = np.load(
            get_segment_center_of_mass_file_path(output_data_folder=self._output_folder_path)
        )

    def _load_full_npy_data(self):
        self.data_frame_name_xyz = np.load(get_full_npy_file_path(output_data_folder=self._output_folder_path))

    def _load_names_and_connections(self):
        with open(self._output_folder_path / "mediapipe_names_and_connections_dict.json", "r") as file:
            self.names_and_connections = json.loads(file.read())

    def _load_segment_lengths(self):
        with open(self._output_folder_path / "mediapipe_skeleton_segment_lengths.json", "r") as file:
            self.segment_lengths = json.loads(file.read())

    def load_frame_data(self, frame_number: int) -> FrameData:
        return FrameData(
            timestamps=self.get_timestamps(frame_number), tracked_points=self.get_tracked_points(frame_number)
        )

    def get_timestamps(self, frame_number):
        try:
            return Timestamps(
                mean=self._timestamps_mean_per_frame[frame_number],
                by_camera={
                    camera_name: timestamps[frame_number]
                    for camera_name, timestamps in self._timestamps_by_camera.items()
                },
            )
        except AttributeError:
            return Timestamps()

    def get_tracked_points(self, frame_number) -> Dict[str, Point]:
        right_hand_points = {}
        left_hand_points = {}
        face_points = {}

        body_points = self._process_dataframe(self.body_dataframe.iloc[frame_number, :])
        center_of_mass_points = self._get_center_of_mass_data(frame_number)

        if self.include_hands:
            left_hand_points, right_hand_points = self._load_hand_data(frame_number)

        if self.include_face:
            face_points = self._process_dataframe(self.face_dataframe.iloc[frame_number, :])

        all_points = {}
        all_points.update(body_points)
        all_points.update(center_of_mass_points)
        all_points.update(right_hand_points)
        all_points.update(left_hand_points)
        all_points.update(face_points)

        return all_points

    def _load_hand_data(self, frame_number: int):
        right_hand_points = self._process_dataframe(self.right_hand_dataframe.iloc[frame_number, :])
        left_hand_points = self._process_dataframe(self.left_hand_dataframe.iloc[frame_number, :])
        return left_hand_points, right_hand_points

    def _get_center_of_mass_data(self, frame_number: int):
        """
        Calculate the center of mass for a given frame number.
        """
        com_data = {}
        com_data["full_body_com"] = Point(
            x=self.center_of_mass_xyz[frame_number, 0],
            y=self.center_of_mass_xyz[frame_number, 1],
            z=self.center_of_mass_xyz[frame_number, 2],
        )

        for segment_number, segment_name in enumerate(BODY_SEGMENT_NAMES):
            com_data[segment_name] = Point(
                x=self.segment_center_of_mass_segment_xyz[frame_number, segment_number, 0],
                y=self.segment_center_of_mass_segment_xyz[frame_number, segment_number, 1],
                z=self.segment_center_of_mass_segment_xyz[frame_number, segment_number, 2],
            )

        return com_data

    def _process_dataframe(self, data_frame) -> Dict[str, Any]:
        """
        Process a single row from a dataframe and add it to the recording_data_by_frame_number dictionary.

        Args:
            data_frame (DataFrame): the dataframe to process.
        """
        tracked_points = {}
        column_names = list(data_frame.index)
        for column_name in column_names:
            point_name = column_name[:-2]  # e.g. "nose" or "left_knee" or whatever
            dimension = column_name[-1]  # e.g. "x" or "y" or "z"

            value = data_frame[column_name]
            if pd.isna(value):  # Check if value is NaN
                value = None  # Replace NaN with None which is valid in JSON

            tracked_points.setdefault(point_name, {})[dimension] = value

        return tracked_points

    def get_data_by_frame(self):
        recording_data_by_frame_number = {}
        for frame_number in range(self.number_of_frames):
            recording_data_by_frame_number[frame_number] = self.load_frame_data(frame_number).to_dict()
        return recording_data_by_frame_number

    def _load_skeleton_schema(self):
        self.skeleton_schema = SkeletonSchema(schema_dict=mediapipe_skeleton_schema)
