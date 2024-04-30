from pathlib import Path
from typing import Dict, List
import logging
import numpy as np
import pandas as pd

from skellytracker.trackers.base_tracker.model_info import ModelInfo

from freemocap.system.paths_and_filenames.file_and_folder_names import (
    BODY_3D_DATAFRAME_CSV_FILE_NAME,
    FACE_3D_DATAFRAME_CSV_FILE_NAME,
    LEFT_HAND_3D_DATAFRAME_CSV_FILE_NAME,
    RIGHT_HAND_3D_DATAFRAME_CSV_FILE_NAME,
)

logger = logging.getLogger(__name__)


# This is dependent on the ordering we currently use for mediapipe, maybe it should live in model_info
category_info = {
    "body": BODY_3D_DATAFRAME_CSV_FILE_NAME,
    "right_hand": RIGHT_HAND_3D_DATAFRAME_CSV_FILE_NAME,
    "left_hand": LEFT_HAND_3D_DATAFRAME_CSV_FILE_NAME,
    "face": FACE_3D_DATAFRAME_CSV_FILE_NAME,
}


def split_data(
    skeleton_3d_data: np.ndarray,
    model_info: ModelInfo,
) -> Dict[str, np.ndarray]:
    """
    Splits the skeleton data into separate arrays for each data category using the provided model info.
    Examples categories are body, left_hand, right_hand, and face.

    Parameters:
    - skeleton: The skeleton data to be split.
    - model_info: The model info used in tracking.

    Returns:
    - A dictionary where each key is a category and the value is the corresponding data array.
    """

    split_data = {}

    # TODO: this function probably shouldn't exist, and its existence implies we should be separately tracking body, hands, and face

    current_index = 0
    for category in category_info.keys():
        tracked_points_name = "num_tracked_points_" + category
        if hasattr(model_info, tracked_points_name):
            prev_index = current_index
            current_index += getattr(model_info, tracked_points_name)
            split_data[category] = skeleton_3d_data[:, prev_index:current_index, :]

    if split_data == {}:
        logger.debug("No data categories found in model info, skipping data splitting")

    return split_data


def create_column_names(model_info: ModelInfo) -> Dict[str, List[str]]:
    """
    Creates a list of column names for the skeleton data based on the model info.

    Parameters:
    - model_info: The model info used in tracking.

    Returns:
    - A list of column names for the skeleton data.
    """

    column_names = {}
    for category in category_info.keys():
        tracked_points_name = "num_tracked_points_" + category
        landmark_names = category + "_landmark_names"
        if hasattr(model_info, tracked_points_name):
            category_column_names = []
            if hasattr(model_info, landmark_names) and len(getattr(model_info, landmark_names)) == getattr(
                model_info, tracked_points_name
            ):
                for name in getattr(model_info, landmark_names):
                    category_column_names.append(f"{category}_{name}_x")
                    category_column_names.append(f"{category}_{name}_y")
                    category_column_names.append(f"{category}_{name}_z")
            else:
                for i in range(getattr(model_info, tracked_points_name)):
                    category_column_names.append(f"{category}_{str(i).zfill(4)}_x")
                    category_column_names.append(f"{category}_{str(i).zfill(4)}_y")
                    category_column_names.append(f"{category}_{str(i).zfill(4)}_z")

            column_names[category] = category_column_names

    return column_names


def save_split_csv(
    output_data_folder_path: str,
    split_data: Dict[str, np.ndarray],
    column_names: Dict[str, List[str]],
    model_info: ModelInfo,
) -> None:
    """
    Saves the split skeleton data to CSV files using column names.

    Parameters:
    - split_data: A dictionary where each key is a category and the value is the corresponding data array.
    - column_names: A dictionary where each key is a category and the value is a list of column names for the data.
    """
    if split_data == {}:
        logger.debug("No data categories found in model info, skipping data splitting")
        return

    number_of_frames = next(iter(split_data.values())).shape[0]

    for category, data in split_data.items():
        column_name_list = column_names[category]
        tracked_points_name = "num_tracked_points_" + category

        data_flat = data.reshape(number_of_frames, getattr(model_info, tracked_points_name) * 3)
        dataframe = pd.DataFrame(data_flat, columns=column_name_list)
        dataframe.to_csv(str(Path(output_data_folder_path) / category_info[category]), index=False)

    logger.info(f"Saved split skeleton data csvs to {output_data_folder_path}")


def save_split_npy(output_data_folder_path: str, split_data: Dict[str, np.ndarray]) -> None:
    """
    Saves the split skeleton data to numpy files.

    Parameters:
    - split_data: A dictionary where each key is a category and the value is the corresponding data array.
    """

    if split_data == {}:
        logger.debug("No data categories found in model info, skipping data splitting")
        return

    for category, data in split_data.items():
        np.save(str(Path(output_data_folder_path) / (category + "_3d_xyz.npy")), data)

    logger.info(f"Saved split skeleton data npys to {output_data_folder_path}")


def split_and_save(
    skeleton_3d_data: np.ndarray,
    model_info: ModelInfo,
    output_data_folder_path: str,
) -> None:
    """
    Splits the skeleton data into separate arrays for each data category using the provided model info.
    Examples categories are body, left_hand, right_hand, and face.
    Then saves the split skeleton data to CSV files using column names.
    Then saves the split skeleton data to numpy files.

    Parameters:
    - skeleton: The skeleton data to be split.
    - model_info: The model info used in tracking.
    - output_data_folder_path: The path to save the split skeleton data to.
    """

    split_data_dict = split_data(skeleton_3d_data, model_info)
    column_names = create_column_names(model_info)
    save_split_csv(output_data_folder_path, split_data_dict, column_names, model_info)
    save_split_npy(output_data_folder_path, split_data_dict)
