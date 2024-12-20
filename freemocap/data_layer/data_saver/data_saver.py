import json
import logging
from pathlib import Path
from typing import Tuple, Union

import numpy as np
import pandas as pd

from skellytracker.trackers.mediapipe_tracker.mediapipe_model_info import (
    MediapipeModelInfo,
)
from skellytracker.trackers.base_tracker.model_info import ModelInfo

from freemocap.data_layer.data_saver.data_loader import DataLoader
from freemocap.data_layer.data_saver.data_models import InfoDict

logger = logging.getLogger(__name__)

from typing import Any, Dict

mediapipe_model_info = MediapipeModelInfo()


class DataSaver:
    def __init__(
        self,
        recording_folder_path: Union[Path, str],
        include_hands: bool = True,
        include_face: bool = True,
        model_info: ModelInfo = mediapipe_model_info,
    ):
        """
        Initialize DataFrameManager with the given recording_folder_path.

        Args:
            recording_folder_path (Union[Path, str]): path to the folder containing the recording data.
            include_hands (bool): flag to include hands data in the processing.
            include_face (bool): flag to include face data in the processing.
        """
        self.recording_folder_path = Path(recording_folder_path)
        self._recording_name = self.recording_folder_path.name

        self._data_loader = DataLoader(
            recording_folder_path=self.recording_folder_path,
            include_hands=include_hands,
            include_face=include_face,
            model_info=model_info,
        )

        self.recording_data_by_frame = None
        self.number_of_frames = None
        self.model_info = model_info

    def save_all(self):
        """
        Load all data, validate it, and create the recording_data_by_frame_number dictionary.

        Returns:
            Dict[int, Dict]: a dictionary containing the processed data, indexed by frame number.
        """

        self.recording_data_by_frame = self._data_loader.get_data_by_frame()

        self.save_to_json()
        self.save_to_csv()
        self.save_to_npy()
        self.save_to_tidy_csv()

    def save_to_json(self, save_path: Union[str, Path] = None):
        dict_to_save = {}
        dict_to_save["info"] = self._get_info_dict().model_dump()
        dict_to_save["data_by_frame"] = self.recording_data_by_frame

        if save_path is None:
            save_path = Path(self.recording_folder_path) / f"{self._recording_name}_by_frame.json"

        logger.info(f"Saving recording data to {save_path}")

        save_path.write_text(json.dumps(dict_to_save, indent=4), encoding="utf-8")

    def save_to_csv(self, save_path: Union[str, Path] = None):
        data_for_dataframe = []

        for frame_data in self.recording_data_by_frame.values():
            data_for_dataframe.append(self._generate_frame_data_row(frame_data))

        # Create DataFrame and save to csv
        df = pd.DataFrame(data_for_dataframe)

        if save_path is None:
            save_path = self.recording_folder_path / f"{self._recording_name}_by_trajectory.csv"

        df.to_csv(save_path, index=False)
        logger.info(f"Saved recording data to {save_path}")

    def _parse_keypoint_name(self, keypoint_name: str) -> Tuple[str, str]:
        if keypoint_name.startswith("right_hand"):
            split_point_name = keypoint_name.split("right_hand_", maxsplit=1)
            model = f"{self.model_info.name}_hand"
            keypoint = f"right_{split_point_name[1]}"
        elif keypoint_name.startswith("left_hand"):
            split_point_name = keypoint_name.split("left_hand_", maxsplit=1)
            model = f"{self.model_info.name}_hand"
            keypoint = f"left_{split_point_name[1]}"
        else:
            split_point_name = keypoint_name.split("_", maxsplit=1)
            if len(split_point_name) != 2:
                model = self.model_info.name
                keypoint = keypoint_name
            else:
                model = f"{self.model_info.name}_{split_point_name[0]}"
                keypoint = split_point_name[1]

        return model, keypoint

    def save_to_tidy_csv(self, save_path: Union[str, Path, None] = None):
        tidy_data = []

        # Iterate over frames and tracked points
        for frame_number, frame_data in self.recording_data_by_frame.items():
            timestamp = frame_data["timestamps"]["mean"]
            timestamp_by_camera = frame_data["timestamps"]["by_camera"]

            for point_name, coordinates in frame_data["tracked_points"].items():
                model, keypoint = self._parse_keypoint_name(point_name)
                tidy_data.append(
                    {
                        "frame": frame_number,
                        "timestamp": timestamp,
                        "timestamp_by_camera": timestamp_by_camera,
                        "model": model,
                        "keypoint": keypoint,
                        "x": coordinates.get("x", None),
                        "y": coordinates.get("y", None),
                        "z": coordinates.get("z", None),
                    }
                )

        # Convert to DataFrame
        tidy_df = pd.DataFrame(tidy_data)

        # Set the save path if not provided
        if save_path is None:
            save_path = self.recording_folder_path / f"{self._recording_name}_by_frame.csv"

        # Save the DataFrame to a CSV file
        tidy_df.to_csv(save_path, index=False)
        logger.info(f"Saved tidy recording data to {save_path}")

    def save_to_npy(self, save_path: Union[str, Path] = None):
        if save_path is None:
            save_path = self.recording_folder_path / f"{self._recording_name}_frame_name_xyz.npy"
        np.save(save_path, self._data_loader.data_frame_name_xyz)
        logger.info(f"Saved recording data to {save_path}")

    def _generate_frame_data_row(self, frame_data: Dict[str, Any]) -> Dict:
        """
        Generate a data row for a given frame number.
        """
        frame_data_row = {}

        frame_data_row["timestamp"] = frame_data["timestamps"]["mean"]
        frame_data_row["timestamp_by_camera"] = str(frame_data["timestamps"]["by_camera"])

        for key, tracked_point in frame_data["tracked_points"].items():
            frame_data_row[f"{key}_x"] = tracked_point["x"]
            frame_data_row[f"{key}_y"] = tracked_point["y"]
            frame_data_row[f"{key}_z"] = tracked_point["z"]

        return frame_data_row

    def _get_info_dict(self):
        return InfoDict(
            # segment_lengths=self._data_loader.segment_lengths,
            schemas=self._data_loader._model_info.segment_connections,
        )


if __name__ == "__main__":
    # recording_data_saver = DataSaver(recording_folder_path=get_sample_data_path())
    recording_data_saver = DataSaver(
        recording_folder_path=r"C:\Users\aaron\FreeMocap_Data\recording_sessions\freemocap_sample_data"
    )
    recording_data_by_frame_number = recording_data_saver.save_all()
