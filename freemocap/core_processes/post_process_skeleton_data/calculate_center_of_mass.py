import logging
from typing import List

import numpy as np
import pandas as pd
from rich.progress import track

from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.data_models.mediapipe_skeleton_names_and_connections import (
    mediapipe_body_landmark_names,
)

logger = logging.getLogger(__name__)


def mediapipe_body_names_match_expected(mediapipe_body_landmark_names: List[str]) -> bool:
    """
    Check if the mediapipe folks have changed their landmark names. If they have, then this function may need to be updated.

    Args:
        mediapipe_body_landmark_names: List of strings, each string is the name of a mediapipe landmark.

    Returns:
        bool: True if the mediapipe landmark names are as expected, False otherwise.
    """
    expected_mediapipe_body_landmark_names = [
        "nose",
        "left_eye_inner",
        "left_eye",
        "left_eye_outer",
        "right_eye_inner",
        "right_eye",
        "right_eye_outer",
        "left_ear",
        "right_ear",
        "mouth_left",
        "mouth_right",
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_wrist",
        "right_wrist",
        "left_pinky",
        "right_pinky",
        "left_index",
        "right_index",
        "left_thumb",
        "right_thumb",
        "left_hip",
        "right_hip",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle",
        "left_heel",
        "right_heel",
        "left_foot_index",
        "right_foot_index",
    ]
    return mediapipe_body_landmark_names == expected_mediapipe_body_landmark_names


def return_indices_of_joints(list_of_indices, list_of_joint_names):
    indices = []
    for name in list_of_joint_names:
        this_name_index = list_of_indices.index(name)
        indices.append(this_name_index)

    return indices


# %%


def return_XYZ_coordinates_of_markers(freemocap_data, indices_list, frame):
    XYZ_coordinates = []
    for index in indices_list:
        this_joint_coordinate = freemocap_data[frame, index, :]
        XYZ_coordinates.append(this_joint_coordinate)

    return XYZ_coordinates


# %%


def build_virtual_trunk_marker(freemocap_data, list_of_indices, trunk_joint_connection, frame):
    trunk_marker_indices = return_indices_of_joints(list_of_indices, trunk_joint_connection)

    trunk_XYZ_coordinates = return_XYZ_coordinates_of_markers(freemocap_data, trunk_marker_indices, frame)

    trunk_proximal = (trunk_XYZ_coordinates[0] + trunk_XYZ_coordinates[1]) / 2
    trunk_distal = (trunk_XYZ_coordinates[2] + trunk_XYZ_coordinates[3]) / 2

    return trunk_proximal, trunk_distal


# %%


def build_mediapipe_skeleton(mediapipe_pose_data, segment_dataframe, mediapipe_indices) -> list:
    """This function takes in the mediapipe pose data array and the segment_conn_len_perc_dataframe.
    For each frame of data, it loops through each segment we want to find and identifies the names
    of the proximal and distal joints of that segment. Then it searches the mediapipe_indices list
    to find the index that corresponds to the name of that segment. We plug the index into the
    mediapipe_pose_data array to find the proximal/distal joints' XYZ coordinates at that frame.
    The segment, its proximal joint and its distal joint gets thrown into a dictionary.
    And then that dictionary gets saved to a list for each frame. By the end of the function, you
    have a list that contains the skeleton segment XYZ coordinates for each frame."""

    num_frames = mediapipe_pose_data.shape[0]
    num_frame_range = range(num_frames)

    mediapipe_frame_segment_joint_XYZ = []  # empty list to hold all the skeleton XYZ coordinates/frame

    for frame in track(num_frame_range, description="Building a MediaPipe Skeleton"):
        trunk_joint_connection = [
            "left_shoulder",
            "right_shoulder",
            "left_hip",
            "right_hip",
        ]
        trunk_virtual_markers = build_virtual_trunk_marker(
            mediapipe_pose_data, mediapipe_indices, trunk_joint_connection, frame
        )

        mediapipe_pose_skeleton_coordinates = {}
        for (
            segment,
            segment_info,
        ) in (
            segment_dataframe.iterrows()
        ):  # iterate through the data frame by the segment name and all the info for that segment
            if segment == "trunk":
                # based on index, extract coordinate data from fmc mediapipe data
                mediapipe_pose_skeleton_coordinates[segment] = [
                    trunk_virtual_markers[0],
                    trunk_virtual_markers[1],
                ]
            elif segment == "left_hand" or segment == "right_hand":
                proximal_joint_hand = segment_info["Joint_Connection"][0]
                if segment == "left_hand":
                    distal_joint_hand = "left_index"
                else:
                    distal_joint_hand = "right_index"

                proximal_joint_hand_index = mediapipe_indices.index(proximal_joint_hand)
                distal_joint_hand_index = mediapipe_indices.index(distal_joint_hand)

                mediapipe_pose_skeleton_coordinates[segment] = [
                    mediapipe_pose_data[frame, proximal_joint_hand_index, :],
                    mediapipe_pose_data[frame, distal_joint_hand_index, :],
                ]

            elif segment == "left_foot" or segment == "right_foot":
                if segment == "left_foot":
                    proximal_joint_foot_name = "left_ankle"
                else:
                    proximal_joint_foot_name = "right_ankle"

                proximal_joint_foot_index = mediapipe_indices.index(proximal_joint_foot_name)

                distal_joint_foot = segment_info["Joint_Connection"][1]
                distal_joint_foot_index = mediapipe_indices.index(distal_joint_foot)
                mediapipe_pose_skeleton_coordinates[segment] = [
                    mediapipe_pose_data[frame, proximal_joint_foot_index, :],
                    mediapipe_pose_data[frame, distal_joint_foot_index, :],
                ]

            else:
                proximal_joint_name = segment_info["Joint_Connection"][0]
                distal_joint_name = segment_info["Joint_Connection"][1]

                # get the mediapipe index for the proximal and distal joint for this segment
                proximal_joint_index = mediapipe_indices.index(proximal_joint_name)
                distal_joint_index = mediapipe_indices.index(distal_joint_name)

                # use the mediapipe indices to get the XYZ coordinates for the prox/distal joints and throw it in a dictionary
                # mediapipe_pose_skeleton_coordinates[segment] = {'proximal':mediapipe_pose_data[frame,proximal_joint_index,:],'distal':mediapipe_pose_data[frame,distal_joint_index,:]}
                mediapipe_pose_skeleton_coordinates[segment] = [
                    mediapipe_pose_data[frame, proximal_joint_index, :],
                    mediapipe_pose_data[frame, distal_joint_index, :],
                ]

        mediapipe_frame_segment_joint_XYZ.append(mediapipe_pose_skeleton_coordinates)

    return mediapipe_frame_segment_joint_XYZ


# %%
# values for segment weight and segment mass percentages taken from Winter anthropometry tables
# https://imgur.com/a/aD74j
# Winter, D.A. (2005) Biomechanics and Motor Control of Human Movement. 3rd Edition, John Wiley & Sons, Inc., Hoboken.


BODY_SEGMENT_NAMES = [
    "head",
    "trunk",
    "right_upper_arm",
    "left_upper_arm",
    "right_forearm",
    "left_forearm",
    "right_hand",
    "left_hand",
    "right_thigh",
    "left_thigh",
    "right_shin",
    "left_shin",
    "right_foot",
    "left_foot",
]

joint_connections = [
    ["left_ear", "right_ear"],
    ["mid_chest_marker", "mid_hip_marker"],
    ["right_shoulder", "right_elbow"],
    ["left_shoulder", "left_elbow"],
    ["right_elbow", "right_wrist"],
    ["left_elbow", "left_wrist"],
    ["right_wrist", "right_hand_marker"],
    ["left_wrist", "left_hand_marker"],
    ["right_hip", "right_knee"],
    ["left_hip", "left_knee"],
    ["right_knee", "right_ankle"],
    ["left_knee", "left_ankle"],
    ["right_back_of_foot_marker", "right_foot_index"],
    ["left_back_of_foot_marker", "left_foot_index"],
]

segment_COM_lengths = [
    0.5,
    0.5,
    0.436,
    0.436,
    0.430,
    0.430,
    0.506,
    0.506,
    0.433,
    0.433,
    0.433,
    0.433,
    0.5,
    0.5,
]

segment_COM_percentages = [
    0.081,
    0.497,
    0.028,
    0.028,
    0.016,
    0.016,
    0.006,
    0.006,
    0.1,
    0.1,
    0.0465,
    0.0465,
    0.0145,
    0.0145,
]


# %%
def calculate_segment_COM(
    segment_conn_len_perc_dataframe,
    skelcoordinates_frame_segment_joint_XYZ,
    num_frame_range,
):
    segment_COM_frame_dict = []
    for frame in track(num_frame_range, description="Calculating Segment Center of Mass"):
        segment_COM_dict = {}
        for segment, segment_info in segment_conn_len_perc_dataframe.iterrows():
            this_segment_XYZ = skelcoordinates_frame_segment_joint_XYZ[frame][segment]

            # for mediapipe
            this_segment_proximal = this_segment_XYZ[0]
            this_segment_distal = this_segment_XYZ[1]
            this_segment_COM_length = segment_info["Segment_COM_Length"]

            this_segment_COM = this_segment_proximal + this_segment_COM_length * (
                this_segment_distal - this_segment_proximal
            )
            segment_COM_dict[segment] = this_segment_COM
        segment_COM_frame_dict.append(segment_COM_dict)
    return segment_COM_frame_dict


# %%


def reformat_segment_COM(segment_COM_frame_dict, num_frame_range, num_segments):
    segment_COM_frame_imgPoint_XYZ = np.empty([int(len(num_frame_range)), int(num_segments), 3])
    for frame in num_frame_range:
        this_frame_skeleton = segment_COM_frame_dict[frame]
        for joint_count, segment in enumerate(this_frame_skeleton.keys()):
            segment_COM_frame_imgPoint_XYZ[frame, joint_count, :] = this_frame_skeleton[segment]
    return segment_COM_frame_imgPoint_XYZ


# %%


def calculate_total_body_COM(segment_conn_len_perc_dataframe, segment_COM_frame_dict, num_frame_range):
    logger.info("Calculating Total Body Center of Mass")
    totalBodyCOM_frame_XYZ = np.empty([int(len(num_frame_range)), 3])

    for frame in track(num_frame_range, description="Calculating Total Body Center of Mass..."):
        this_frame_total_body_percentages = []
        this_frame_skeleton = segment_COM_frame_dict[frame]

        for segment, segment_info in segment_conn_len_perc_dataframe.iterrows():
            this_segment_COM = this_frame_skeleton[segment]
            this_segment_COM_percentage = segment_info["Segment_COM_Percentage"]

            this_segment_total_body_percentage = this_segment_COM * this_segment_COM_percentage
            this_frame_total_body_percentages.append(this_segment_total_body_percentage)

        this_frame_total_body_COM = np.nansum(this_frame_total_body_percentages, axis=0)

        totalBodyCOM_frame_XYZ[frame, :] = this_frame_total_body_COM

    return totalBodyCOM_frame_XYZ


# %%


def build_anthropometric_dataframe(
    segments: list,
    joint_connections: list,
    segment_COM_lengths: list,
    segment_COM_percentages: list,
) -> pd.DataFrame:
    # load anthropometric data into a pandas dataframe
    df = pd.DataFrame(
        list(
            zip(
                segments,
                joint_connections,
                segment_COM_lengths,
                segment_COM_percentages,
            )
        ),
        columns=[
            "Segment_Name",
            "Joint_Connection",
            "Segment_COM_Length",
            "Segment_COM_Percentage",
        ],
    )
    segment_conn_len_perc_dataframe = df.set_index("Segment_Name")
    return segment_conn_len_perc_dataframe


def calculate_center_of_mass(
    freemocap_marker_data_array: np.ndarray,
    pose_estimation_skeleton: list,
    anthropometric_info_dataframe: pd.DataFrame,
):
    num_frames = freemocap_marker_data_array.shape[0]
    num_frame_range = range(num_frames)
    num_segments = len(anthropometric_info_dataframe)

    segment_COM_frame_dict = calculate_segment_COM(
        anthropometric_info_dataframe, pose_estimation_skeleton, num_frame_range
    )
    segment_COM_frame_imgPoint_XYZ = reformat_segment_COM(segment_COM_frame_dict, num_frame_range, num_segments)
    totalBodyCOM_frame_XYZ = calculate_total_body_COM(
        anthropometric_info_dataframe, segment_COM_frame_dict, num_frame_range
    )

    return (
        segment_COM_frame_dict,
        segment_COM_frame_imgPoint_XYZ,
        totalBodyCOM_frame_XYZ,
    )


def run_center_of_mass_calculations(processed_skel3d_frame_marker_xyz: np.ndarray):
    anthropometric_info_dataframe = build_anthropometric_dataframe(
        BODY_SEGMENT_NAMES, joint_connections, segment_COM_lengths, segment_COM_percentages
    )
    if not mediapipe_body_names_match_expected(mediapipe_body_landmark_names):
        raise ValueError(
            "Mediapipe body landmark names do not match expected names - Perhaps they altered the names in a new version? This code will need to be updated"
        )

    skelcoordinates_frame_segment_joint_XYZ = build_mediapipe_skeleton(
        processed_skel3d_frame_marker_xyz,
        anthropometric_info_dataframe,
        mediapipe_body_landmark_names,
    )
    (
        segment_COM_frame_dict,
        segment_COM_frame_imgPoint_XYZ,
        totalBodyCOM_frame_XYZ,
    ) = calculate_center_of_mass(
        processed_skel3d_frame_marker_xyz,
        skelcoordinates_frame_segment_joint_XYZ,
        anthropometric_info_dataframe,
    )

    return segment_COM_frame_imgPoint_XYZ, totalBodyCOM_frame_XYZ
