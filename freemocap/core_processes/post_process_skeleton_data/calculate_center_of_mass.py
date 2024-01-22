import logging
import numpy as np
import pandas as pd
from rich.progress import track

# TODO: Generalize references to generic Model Info class and parameterize the tracker type
from skellytracker.trackers.mediapipe_tracker.mediapipe_model_info import MediapipeModelInfo

logger = logging.getLogger(__name__)


def return_indices_of_joints(list_of_indices, list_of_joint_names):
    indices = []
    for name in list_of_joint_names:
        this_name_index = list_of_indices.index(name)
        indices.append(this_name_index)

    return indices


def return_XYZ_coordinates_of_markers(freemocap_data, indices_list, frame):
    XYZ_coordinates = []
    for index in indices_list:
        this_joint_coordinate = freemocap_data[frame, index, :]
        XYZ_coordinates.append(this_joint_coordinate)

    return XYZ_coordinates


def build_virtual_trunk_marker(freemocap_data, list_of_indices, trunk_joint_connection, frame):
    trunk_marker_indices = return_indices_of_joints(list_of_indices, trunk_joint_connection)

    trunk_XYZ_coordinates = return_XYZ_coordinates_of_markers(freemocap_data, trunk_marker_indices, frame)

    trunk_proximal = (trunk_XYZ_coordinates[0] + trunk_XYZ_coordinates[1]) / 2
    trunk_distal = (trunk_XYZ_coordinates[2] + trunk_XYZ_coordinates[3]) / 2

    return trunk_proximal, trunk_distal


def build_skeleton(pose_data, segment_dataframe, body_indices) -> list:
    """This function takes in the image pose data array and the segment_conn_len_perc_dataframe.
    For each frame of data, it loops through each segment we want to find and identifies the names
    of the proximal and distal joints of that segment. Then it searches the indices list
    to find the index that corresponds to the name of that segment. We plug the index into the
    pose_data array to find the proximal/distal joints' XYZ coordinates at that frame.
    The segment, its proximal joint and its distal joint gets thrown into a dictionary.
    And then that dictionary gets saved to a list for each frame. By the end of the function, you
    have a list that contains the skeleton segment XYZ coordinates for each frame."""

    num_frames = pose_data.shape[0]
    num_frame_range = range(num_frames)

    frame_segment_joint_XYZ = []  # empty list to hold all the skeleton XYZ coordinates/frame

    for frame in track(num_frame_range, description="Building Skeleton"):
        # TODO: generalize this to work with any number of body joints/names
        trunk_joint_connection = [
            "left_shoulder",
            "right_shoulder",
            "left_hip",
            "right_hip",
        ]
        trunk_virtual_markers = build_virtual_trunk_marker(pose_data, body_indices, trunk_joint_connection, frame)

        pose_skeleton_coordinates = {}
        for (
            segment,
            segment_info,
        ) in (
            segment_dataframe.iterrows()
        ):  # iterate through the data frame by the segment name and all the info for that segment
            if segment == "trunk":
                # based on index, extract coordinate data from fmc data
                pose_skeleton_coordinates[segment] = [
                    trunk_virtual_markers[0],
                    trunk_virtual_markers[1],
                ]
            elif segment == "left_hand" or segment == "right_hand":
                proximal_joint_hand = segment_info["Joint_Connection"][0]
                if segment == "left_hand":
                    distal_joint_hand = "left_index"
                else:
                    distal_joint_hand = "right_index"

                proximal_joint_hand_index = body_indices.index(proximal_joint_hand)
                distal_joint_hand_index = body_indices.index(distal_joint_hand)

                pose_skeleton_coordinates[segment] = [
                    pose_data[frame, proximal_joint_hand_index, :],
                    pose_data[frame, distal_joint_hand_index, :],
                ]

            elif segment == "left_foot" or segment == "right_foot":
                if segment == "left_foot":
                    proximal_joint_foot_name = "left_ankle"
                else:
                    proximal_joint_foot_name = "right_ankle"

                proximal_joint_foot_index = body_indices.index(proximal_joint_foot_name)

                distal_joint_foot = segment_info["Joint_Connection"][1]
                distal_joint_foot_index = body_indices.index(distal_joint_foot)
                pose_skeleton_coordinates[segment] = [
                    pose_data[frame, proximal_joint_foot_index, :],
                    pose_data[frame, distal_joint_foot_index, :],
                ]

            else:
                proximal_joint_name = segment_info["Joint_Connection"][0]
                distal_joint_name = segment_info["Joint_Connection"][1]

                # get the index for the proximal and distal joint for this segment
                proximal_joint_index = body_indices.index(proximal_joint_name)
                distal_joint_index = body_indices.index(distal_joint_name)

                # use the indices to get the XYZ coordinates for the prox/distal joints and throw it in a dictionary
                pose_skeleton_coordinates[segment] = [
                    pose_data[frame, proximal_joint_index, :],
                    pose_data[frame, distal_joint_index, :],
                ]

        frame_segment_joint_XYZ.append(pose_skeleton_coordinates)

    return frame_segment_joint_XYZ


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

            this_segment_proximal = this_segment_XYZ[0]
            this_segment_distal = this_segment_XYZ[1]
            this_segment_COM_length = segment_info["Segment_COM_Length"]

            this_segment_COM = this_segment_proximal + this_segment_COM_length * (
                this_segment_distal - this_segment_proximal
            )
            segment_COM_dict[segment] = this_segment_COM
        segment_COM_frame_dict.append(segment_COM_dict)
    return segment_COM_frame_dict


def reformat_segment_COM(segment_COM_frame_dict, num_frame_range, num_segments):
    segment_COM_frame_imgPoint_XYZ = np.empty([int(len(num_frame_range)), int(num_segments), 3])
    for frame in num_frame_range:
        this_frame_skeleton = segment_COM_frame_dict[frame]
        for joint_count, segment in enumerate(this_frame_skeleton.keys()):
            segment_COM_frame_imgPoint_XYZ[frame, joint_count, :] = this_frame_skeleton[segment]
    return segment_COM_frame_imgPoint_XYZ


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
        MediapipeModelInfo.segment_names,
        MediapipeModelInfo.joint_connections,
        MediapipeModelInfo.segment_COM_lengths,
        MediapipeModelInfo.segment_COM_percentages,
    )

    skelcoordinates_frame_segment_joint_XYZ = build_skeleton(
        processed_skel3d_frame_marker_xyz,
        anthropometric_info_dataframe,
        MediapipeModelInfo.body_landmark_names,
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
