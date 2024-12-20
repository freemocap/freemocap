import logging
from pathlib import Path
from typing import Union, Dict, Any

import numpy as np
import pandas as pd
from skellytracker.trackers.mediapipe_tracker.mediapipe_model_info import (
    MediapipeModelInfo,
)
from skellytracker.trackers.base_tracker.model_info import ModelInfo

from freemocap.data_layer.data_saver.data_models import FrameData, Timestamps, Point, SkeletonSchema
from freemocap.system.paths_and_filenames.file_and_folder_names import (
    BODY_3D_DATAFRAME_CSV_FILE_NAME,
    CENTER_OF_MASS_FOLDER_NAME,
    DATA_3D_NPY_FILE_NAME,
    RIGHT_HAND_3D_DATAFRAME_CSV_FILE_NAME,
    LEFT_HAND_3D_DATAFRAME_CSV_FILE_NAME,
    FACE_3D_DATAFRAME_CSV_FILE_NAME,
    SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME,
    TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME,
)
from freemocap.system.paths_and_filenames.path_getters import (
    get_output_data_folder_path,
    get_timestamps_directory,
)

logger = logging.getLogger(__name__)


# TODO: Need to generalize this beyond mediapipe, and make COM data optional
mediapipe_model_info = MediapipeModelInfo()


class DataLoader:
    def __init__(
        self,
        recording_folder_path: Union[str, Path],
        include_hands: bool = True,
        include_face: bool = True,
        include_com: bool = True,
        model_info: ModelInfo = mediapipe_model_info,
    ):
        self._recording_folder_path = Path(recording_folder_path)
        self.include_hands = include_hands
        self.include_face = include_face
        self.include_com = include_com
        self._model_info = model_info

        self._recording_name = self._recording_folder_path.name
        self._output_folder_path = Path(get_output_data_folder_path(self._recording_folder_path))
        self.number_of_frames = None

        self._set_file_prefix()
        self._load_data()

    def _load_data(self):
        self._load_timestamps()
        self._load_data_frames()
        self._load_full_npy_data()
        self._load_center_of_mass_data()
        # self._load_segment_lengths()
        # self._load_skeleton_schema()
        self._validate_data()

    def _load_data_frames(self):
        self.body_dataframe = self._load_dataframe(self._file_prefix + BODY_3D_DATAFRAME_CSV_FILE_NAME)
        self.number_of_frames = len(self.body_dataframe)
        if self.include_hands:
            try:
                self.right_hand_dataframe = self._load_dataframe(self._file_prefix + RIGHT_HAND_3D_DATAFRAME_CSV_FILE_NAME)
                self.left_hand_dataframe = self._load_dataframe(self._file_prefix + LEFT_HAND_3D_DATAFRAME_CSV_FILE_NAME)
            except FileNotFoundError:
                logger.warning("Unable to load hand data from file.")
                self.right_hand_dataframe = None
                self.left_hand_dataframe = None
                self.include_hands = False
        if self.include_face:
            try:
                self.face_dataframe = self._load_dataframe(self._file_prefix + FACE_3D_DATAFRAME_CSV_FILE_NAME)
            except FileNotFoundError:
                logger.warning("Unable to load face data from file.")
                self.face_dataframe = None
                self.include_face = False

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
                f"The number of frames in the {df_name} dataframe ({len(df)}) is different from the expected number of frames ({self.number_of_frames})."
            )

    def _validate_numpy_array(self, np_array, np_array_name):
        if np_array is not None and np_array.shape[0] != self.number_of_frames:
            print(f"\n\n {np_array.shape} \n\n")
            raise ValueError(
                f"The number of frames in the {np_array_name} data ({np_array.shape[0]}) is different from the expected number of frames ({self.number_of_frames})."
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
        try:
            self.center_of_mass_xyz = np.load(
                self._output_folder_path / CENTER_OF_MASS_FOLDER_NAME / (self._file_prefix + TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME)
            )
            self.segment_center_of_mass_segment_xyz = np.load(
                self._output_folder_path / CENTER_OF_MASS_FOLDER_NAME / (self._file_prefix + SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME)
            )
        except FileNotFoundError:
            logger.warning("Unable to load center of mass data from file.")
            self.center_of_mass_xyz = None
            self.segment_center_of_mass_segment_xyz = None
            self.include_com = False

    def _load_full_npy_data(self):
        self.data_frame_name_xyz = np.load(self._output_folder_path / (self._file_prefix + DATA_3D_NPY_FILE_NAME))

        if not self.number_of_frames:
            self.number_of_frames = self.data_frame_name_xyz.shape[0]

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
            return Timestamps(mean=None)

    def get_tracked_points(self, frame_number) -> Dict[str, Point]:
        right_hand_points = {}
        left_hand_points = {}
        face_points = {}
        center_of_mass_points = {}

        body_points = self._process_dataframe(self.body_dataframe.iloc[frame_number, :])

        if self.include_com:
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
        com_data["com_full_body"] = Point(
            x=self.center_of_mass_xyz[frame_number, 0],
            y=self.center_of_mass_xyz[frame_number, 1],
            z=self.center_of_mass_xyz[frame_number, 2],
        )

        if self._model_info.center_of_mass_definitions is None:
            raise ValueError("center of mass definitions are not provided.")

        for segment_number, segment_name in enumerate(self._model_info.center_of_mass_definitions.keys()):
            com_data[f'com_{segment_name}'] = Point(
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

    def _load_skeleton_schema(self):  # TODO: replace this with updated Skeleton class
        self.skeleton_schema = SkeletonSchema(schema_dict=MediapipeModelInfo.skeleton_schema)

    def _set_file_prefix(self) -> None:
        self._file_prefix = self._model_info.name

        if self._file_prefix[-1] != "_":
            self._file_prefix += "_"
