import json
import logging
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from freemocap.data_layer.data_saver.data_loader import DataLoader
from freemocap.data_layer.data_saver.data_models import InfoDict

logger = logging.getLogger(__name__)

from typing import Any, Dict


class DataSaver:
    def __init__(self, recording_folder_path: Union[Path, str], include_hands: bool = True, include_face: bool = True):
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
            recording_folder_path=self.recording_folder_path, include_hands=include_hands, include_face=include_face
        )

        self.recording_data_by_frame = None
        self.number_of_frames = None

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

    def save_to_json(self, save_path: Union[str, Path] = None):
        dict_to_save = {}
        dict_to_save["info"] = self._get_info_dict().dict()
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
            segment_lengths=self._data_loader.segment_lengths,
            schemas=[self._data_loader.skeleton_schema.dict()],
        )


if __name__ == "__main__":
    # recording_data_saver = DataSaver(recording_folder_path=get_sample_data_path())
    recording_data_saver = DataSaver(
        recording_folder_path=r"C:\Users\jonma\freemocap_data\recording_sessions\session_2023-04-14_15_29_45\recording_15_47_37_gmt-4"
    )
    recording_data_by_frame_number = recording_data_saver.save_all()
