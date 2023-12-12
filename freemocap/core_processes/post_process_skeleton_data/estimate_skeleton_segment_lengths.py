import logging
from pathlib import Path

import numpy as np
import pandas as pd
from rich import print

logger = logging.getLogger(__name__)

mediapipe_skeleton_segment_definitions = {
    "lower_spine": {"proximal": "hips_center", "distal": "chest_center"},
    "upper_spine": {"proximal": "chest_center", "distal": "neck_center"},
    "head": {"proximal": "neck_center", "distal": "head_center"},
    "left_clavicle": {"proximal": "neck_center", "distal": "left_shoulder"},
    "left_upper_arm": {"proximal": "left_shoulder", "distal": "left_elbow"},
    "left_forearm": {"proximal": "left_elbow", "distal": "left_wrist"},
    "left_hand": {"proximal": "left_wrist", "distal": "left_index"},
    "right_clavicle": {"proximal": "neck_center", "distal": "right_shoulder"},
    "right_upper_arm": {"proximal": "right_shoulder", "distal": "right_elbow"},
    "right_forearm": {"proximal": "right_elbow", "distal": "right_wrist"},
    "right_hand": {"proximal": "right_wrist", "distal": "right_index"},
    "left_pelvis": {"proximal": "hips_center", "distal": "left_hip"},
    "left_thigh": {"proximal": "left_hip", "distal": "left_knee"},
    "left_calf": {"proximal": "left_knee", "distal": "left_ankle"},
    "left_foot": {"proximal": "left_ankle", "distal": "left_foot_index"},
    "right_pelvis": {"proximal": "hips_center", "distal": "right_hip"},
    "right_thigh": {"proximal": "right_hip", "distal": "right_knee"},
    "right_calf": {"proximal": "right_knee", "distal": "right_ankle"},
    "right_foot": {"proximal": "right_ankle", "distal": "right_foot_index"},
}


def estimate_skeleton_segment_lengths(skeleton_dataframe: pd.DataFrame, skeleton_segment_definitions: dict) -> dict:
    """Estimate the length of each skeleton segment.

    Args:
        skeleton_data_dictionary (dict): Dictionary containing the skeleton data.
        skeleton_segment_definitions (dict): Dictionary containing the definitions of each segment (i.e. the proximal and distal joints).

    Returns:
        dict: Dictionary containing the estimated length of each skeleton segment.
    """
    logger.debug("Estimating skeleton segment lengths (mm)...")
    skeleton_data_dictionary = create_skeleton_dictionary_from_skeleton_body_data_frame(skeleton_dataframe)

    skeleton_segment_lengths_dict = {}
    for segment_name, segment_definition_dict in skeleton_segment_definitions.items():
        print(
            f"Estimating length of segment '{segment_name}' "
            f"based on proximal joint: '{segment_definition_dict['proximal']}' and "
            f"distal joint:'{segment_definition_dict['distal']}'"
        )
        proximal_joint_name = segment_definition_dict["proximal"]
        distal_joint_name = segment_definition_dict["distal"]

        proximal_x = skeleton_data_dictionary[f"{proximal_joint_name}_x"]
        proximal_y = skeleton_data_dictionary[f"{proximal_joint_name}_y"]
        proximal_z = skeleton_data_dictionary[f"{proximal_joint_name}_z"]

        distal_x = skeleton_data_dictionary[f"{distal_joint_name}_x"]
        distal_y = skeleton_data_dictionary[f"{distal_joint_name}_y"]
        distal_z = skeleton_data_dictionary[f"{distal_joint_name}_z"]

        # logger.debug(f"proximal_x nans: {np.isnan(proximal_x).sum()}")
        # logger.debug(f"len proximal_x: {len(proximal_x)}")
        # logger.debug(f"distal_x nans: {np.isnan(distal_x).sum()}")
        # logger.debug(f"len distal_x: {len(distal_x)}")

        # good ol pythag <3
        segment_length_per_frame = np.sqrt(
            (proximal_x - distal_x) ** 2 + (proximal_y - distal_y) ** 2 + (proximal_z - distal_z) ** 2
        )
        skeleton_segment_lengths_dict[segment_name] = {}
        skeleton_segment_lengths_dict[segment_name]["median"] = np.nanmedian(segment_length_per_frame)
        skeleton_segment_lengths_dict[segment_name]["mean"] = np.nanmean(segment_length_per_frame)
        skeleton_segment_lengths_dict[segment_name]["standard_deviation"] = np.nanstd(segment_length_per_frame)

    return skeleton_segment_lengths_dict


def create_virtual_markers(skeleton_data_dictionary, virtual_marker_name: str, marker_name_list: list) -> dict:
    # print(
    #     f"Creating virtual marker '{virtual_marker_name}' from markers: {marker_name_list}"
    # )

    x = []
    y = []
    z = []

    for marker_name in marker_name_list:
        x.append(skeleton_data_dictionary[f"{marker_name}_x"])
        y.append(skeleton_data_dictionary[f"{marker_name}_y"])
        z.append(skeleton_data_dictionary[f"{marker_name}_z"])

    skeleton_data_dictionary[f"{virtual_marker_name}_x"] = np.nanmean(np.asarray(x), axis=0)
    skeleton_data_dictionary[f"{virtual_marker_name}_y"] = np.nanmean(np.asarray(y), axis=0)
    skeleton_data_dictionary[f"{virtual_marker_name}_z"] = np.nanmean(np.asarray(z), axis=0)

    return skeleton_data_dictionary


def create_skeleton_dictionary_from_skeleton_body_data_frame(
    skeleton_body_dataframe: pd.DataFrame,
) -> dict:
    skeleton_data_dictionary = skeleton_body_dataframe.to_dict(orient="list")

    for key, value in skeleton_data_dictionary.items():
        skeleton_data_dictionary[key] = np.asarray(value)

    skeleton_data_dictionary = create_virtual_markers(
        skeleton_data_dictionary, "hips_center", ["left_hip", "right_hip"]
    )
    skeleton_data_dictionary = create_virtual_markers(
        skeleton_data_dictionary, "neck_center", ["left_shoulder", "right_shoulder"]
    )
    skeleton_data_dictionary = create_virtual_markers(
        skeleton_data_dictionary, "head_center", ["left_ear", "right_ear"]
    )

    skeleton_data_dictionary = create_virtual_markers(
        skeleton_data_dictionary, "chest_center", ["hips_center", "neck_center"]
    )
    return skeleton_data_dictionary


if __name__ == "__main__":
    path_to_skeleton_body_csv = Path(
        r"D:\Dropbox\FreeMoCapProject\teddy_animation\FreeMocap_Data\sesh_2022-10-09_13_55_45_calib_and_take_1_alpha\output_data\mediapipe_body_3d_xyz.csv"
    )
    skeleton_dataframe = pd.read_csv(path_to_skeleton_body_csv)

    skeleton_segment_lengths = estimate_skeleton_segment_lengths(
        skeleton_dataframe, mediapipe_skeleton_segment_definitions
    )

    print(skeleton_segment_lengths)
