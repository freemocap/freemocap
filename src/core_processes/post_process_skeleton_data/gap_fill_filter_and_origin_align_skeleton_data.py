# %%
import logging
from pathlib import Path
import pickle
from typing import Union

import numpy as np
import pandas as pd
from rich.progress import track
from scipy import signal

logger = logging.getLogger(__name__)


# %%
def interpolate_freemocap_data(freemocap_marker_data: np.ndarray) -> np.ndarray:
    """Takes in a 3d skeleton numpy array from freemocap and interpolates missing NaN values"""
    num_frames = freemocap_marker_data.shape[0]
    num_markers = freemocap_marker_data.shape[1]

    freemocap_interpolated_data = np.empty((num_frames, num_markers, 3))

    for marker in track(range(num_markers), description="Interpolating Data"):
        this_marker_skel3d_data = freemocap_marker_data[:, marker, :]

        df = pd.DataFrame(this_marker_skel3d_data)
        df2 = df.interpolate(
            method="linear", axis=0
        )  # use pandas interpolation methods to fill in missing data
        this_marker_interpolated_skel3d_array = np.array(df2)
        # replace the remaining NaN values (the ones that often happen at the start of the recording)
        this_marker_interpolated_skel3d_array = np.where(
            np.isfinite(this_marker_interpolated_skel3d_array),
            this_marker_interpolated_skel3d_array,
            np.nanmean(this_marker_interpolated_skel3d_array),
        )

        freemocap_interpolated_data[
            :, marker, :
        ] = this_marker_interpolated_skel3d_array

    return freemocap_interpolated_data


# %%
def butterworth_lowpass_zerolag_filter(data, cutoff, sampling_rate, order):
    """Run a low pass butterworth filter on a single column of data"""
    nyquist_freq = 0.5 * sampling_rate
    normal_cutoff = cutoff / nyquist_freq
    # Get the filter coefficients
    b, a = signal.butter(order, normal_cutoff, btype="low", analog=False)
    y = signal.filtfilt(b, a, data)
    return y


def filter_skeleton(skeleton_3d_data, cutoff, sampling_rate, order):
    """Take in a 3d skeleton numpy array and run a low pass butterworth filter on each marker in the data"""
    num_frames = skeleton_3d_data.shape[0]
    num_markers = skeleton_3d_data.shape[1]
    filtered_data = np.empty((num_frames, num_markers, 3))

    for marker in range(num_markers):
        for x in range(3):
            filtered_data[:, marker, x] = butterworth_lowpass_zerolag_filter(
                skeleton_3d_data[:, marker, x], cutoff, sampling_rate, order
            )

    return filtered_data


# %%
def find_velocity_values_within_limit(skeleton_velocity_data, velocity_limit):
    """
    This function takes in a skeleton velocity data array and a limit and returns the indices of the values that are within the limit
    """
    indices = []
    for i in range(len(skeleton_velocity_data)):
        if abs(skeleton_velocity_data[i]) <= velocity_limit:
            indices.append(
                i + 1
            )  # add 1 to account for the difference in indices between the position and velocity data
    return indices


# %%


def find_matching_indices_in_lists(list_1, list_2, list_3, list_4):
    """
    This function takes in four lists and returns the indices of the values that are in all four lists
    """
    matching_values = [x for x in list_1 if x in list_2 and x in list_3 and x in list_4]

    return matching_values


# %%


def find_best_velocity_guess(
    skeleton_velocity_data, skeleton_indices, velocity_guess, iteration_range
):
    """
    This function iterates over velocity data and tries to pare down to a single frame that has the closest velocity to 0 for all foot markers
    """

    print(f"Velocity guess: {velocity_guess}, iteration range: {iteration_range}")

    right_heel_index = skeleton_indices.index("right_heel")
    right_toe_index = skeleton_indices.index("right_foot_index")
    left_heel_index = skeleton_indices.index("left_heel")
    left_toe_index = skeleton_indices.index("left_foot_index")

    skeleton_data_velocity_x_right_heel = skeleton_velocity_data[:, right_heel_index, 0]
    skeleton_data_velocity_x_right_toe = skeleton_velocity_data[:, right_toe_index, 0]
    skeleton_data_velocity_x_left_heel = skeleton_velocity_data[:, left_heel_index, 0]
    skeleton_data_velocity_x_left_toe = skeleton_velocity_data[:, left_toe_index, 0]

    print(
        f"sum nan right heel: {np.sum(np.isnan(skeleton_data_velocity_x_right_heel))}, "
        f"sum nan right toe: {np.sum(np.isnan(skeleton_data_velocity_x_right_toe))}, "
        f"sum nan left heel: {np.sum(np.isnan(skeleton_data_velocity_x_left_heel))}, "
        f"sum nan left toe: {np.sum(np.isnan(skeleton_data_velocity_x_left_toe))}, "
        f"num frames: {len(skeleton_data_velocity_x_right_heel)}"
    )

    # get a list of the frames where the velocity for that marker is within the velocity limit
    right_heel_x_velocity_limits = find_velocity_values_within_limit(
        skeleton_data_velocity_x_right_heel, velocity_guess
    )
    right_toe_x_velocity_limits = find_velocity_values_within_limit(
        skeleton_data_velocity_x_right_toe, velocity_guess
    )
    left_heel_x_velocity_limits = find_velocity_values_within_limit(
        skeleton_data_velocity_x_left_heel, velocity_guess
    )
    left_toe_x_velocity_limits = find_velocity_values_within_limit(
        skeleton_data_velocity_x_left_toe, velocity_guess
    )

    # return a list of matching frame indices from the four lists generated above
    matching_values = find_matching_indices_in_lists(
        right_heel_x_velocity_limits,
        right_toe_x_velocity_limits,
        left_heel_x_velocity_limits,
        left_toe_x_velocity_limits,
    )
    matching_values = [x for x in matching_values if x > 75]

    # print(matching_values)
    if len(matching_values) > 1 and velocity_guess > 0:
        # if there are multiple matching values, decrease the guess a little bit and run the function again
        #
        velocity_guess = velocity_guess - iteration_range
        print(
            "Current Velocity Guess:",
            velocity_guess,
            "| Number of Possible Frames:",
            len(matching_values),
            "| Possible Frames:",
            matching_values,
        )
        matching_values, velocity_guess = find_best_velocity_guess(
            skeleton_velocity_data, skeleton_indices, velocity_guess, iteration_range
        )

        f = 2
    elif len(matching_values) == 0:
        # if there are no matching values (we decreased our guess too far), reset the guess to be a bit smaller and run the function again with smaller intervals between the guesses
        iteration_range = iteration_range / 2
        matching_values, velocity_guess = find_best_velocity_guess(
            skeleton_velocity_data,
            skeleton_indices,
            velocity_guess + iteration_range * 2,
            iteration_range,
        )

        f = 2
    elif len(matching_values) == 1:
        print("Good Frame:", matching_values, "| Final Velocity Guess:", velocity_guess)

    return matching_values, velocity_guess


# %%


def find_good_frame(
    skeleton_data, skeleton_indices: list, initial_velocity_guess: float, debug=False
):
    """
    Finds a frame (called the good frame) where the velocity of both feet are closest to 0

    Input:
        skeleton data: a 3D numpy array of skeleton data in freemocap format
        skeleton indices: a list of joints being tracked by mediapipe/your 2d pose estimator
        initial velocity guess: just a starting guess for the optimizer. Can adjust if you're not getting the results you want
        debug: plots and displays the calculated good frame if True
    """

    skeleton_velocity_data = np.diff(skeleton_data, axis=0)
    print("finding best velocity guess...")
    matching_values, velocity_guess = find_best_velocity_guess(
        skeleton_velocity_data,
        skeleton_indices,
        initial_velocity_guess,
        iteration_range=0.1,
    )
    print(f"Return values: {matching_values}")
    good_frame = matching_values[0]

    return good_frame


# %%


def create_vector(point1, point2):
    """Put two points in, make a vector"""
    vector = point2 - point1
    return vector


# %%


def calculate_unit_vector(vector):
    """Take in a vector, make it a unit vector"""
    unit_vector = vector / np.linalg.norm(vector)
    return unit_vector


# %%


def calculate_shoulder_center_XYZ_coordinates(
    single_frame_skeleton_data, left_shoulder_index, right_shoulder_index
):
    """Take in the left and right shoulder indices, and calculate the shoulder center point"""
    left_shoulder_point = single_frame_skeleton_data[left_shoulder_index, :]
    right_shoulder_point = single_frame_skeleton_data[right_shoulder_index, :]
    shoulder_center_XYZ_coordinates = (left_shoulder_point + right_shoulder_point) / 2

    return shoulder_center_XYZ_coordinates


# %%


def calculate_mid_hip_XYZ_coordinates(
    single_frame_skeleton_data, left_hip_index, right_hip_index
):
    """Take in the left and right hip indices, and calculate the mid hip point"""
    left_hip_point = single_frame_skeleton_data[left_hip_index, :]
    right_hip_point = single_frame_skeleton_data[right_hip_index, :]
    mid_hip_XYZ_coordinates = (left_hip_point + right_hip_point) / 2

    return mid_hip_XYZ_coordinates


# %%


def calculate_mid_foot_XYZ_coordinate(
    single_frame_skeleton_data,
    left_heel_index,
    right_heel_index,
):
    """Take in the primary and secondary foot indices, and calculate the mid foot point"""
    right_foot_point = single_frame_skeleton_data[right_heel_index, :]
    left_foot_point = single_frame_skeleton_data[left_heel_index, :]
    mid_foot_XYZ_coordinates = (right_foot_point + left_foot_point) / 2

    return mid_foot_XYZ_coordinates


# def calculate_translation_distance(skeleton_point_coordinate):
#     """Take a skeleton point coordinate and calculate its distance to the origin"""

#     translation_distance = skeleton_point_coordinate - [0,0,0]
#     return translation_distance


# %%


def translate_skeleton_frame(rotated_skeleton_data_frame, translation_distance):
    """Take in a frame of rotated skeleton data, and apply the translation distance to each point in the skeleton"""

    translated_skeleton_frame = rotated_skeleton_data_frame - translation_distance
    return translated_skeleton_frame


# %%


def translate_skeleton_to_origin(point_to_translate, original_skeleton_data):
    num_frames = original_skeleton_data.shape[0]

    translated_skeleton_data = np.zeros(original_skeleton_data.shape)

    for frame in track(range(num_frames), description="Translating Skeleton"):
        translated_skeleton_data[frame, :, :] = translate_skeleton_frame(
            original_skeleton_data[frame, :, :], point_to_translate
        )

    return translated_skeleton_data


# %%


def calculate_skewed_symmetric_cross_product(cross_product_vector):
    # needed in the calculate_rotation_matrix function
    skew_symmetric_cross_product = np.array(
        [
            [0, -cross_product_vector[2], cross_product_vector[1]],
            [cross_product_vector[2], 0, -cross_product_vector[0]],
            [-cross_product_vector[1], cross_product_vector[0], 0],
        ]
    )
    return skew_symmetric_cross_product


# %%


def calculate_rotation_matrix(vector1, vector2):
    """Put in two vectors to calculate the rotation matrix between those two vectors"""
    # based on the code found here: https://math.stackexchange.com/questions/180418/calculate-rotation-matrix-to-align-vector-a-to-vector-b-in-3d"""

    identity_matrix = np.identity(3)
    vector_cross_product = np.cross(vector1, vector2)
    vector_dot_product = np.dot(vector1, vector2)
    skew_symmetric_cross_product = calculate_skewed_symmetric_cross_product(
        vector_cross_product
    )
    rotation_matrix = (
        identity_matrix
        + skew_symmetric_cross_product
        + (np.dot(skew_symmetric_cross_product, skew_symmetric_cross_product))
        * (1 - vector_dot_product)
        / (np.linalg.norm(vector_cross_product) ** 2)
    )

    return rotation_matrix


# %%


def rotate_point(point, rotation_matrix):
    rotated_point = np.dot(rotation_matrix, point)
    return rotated_point


# %%


def rotate_skeleton_frame(this_frame_aligned_skeleton_data, rotation_matrix):
    """Take in a frame of skeleton data, and apply the rotation matrix to each point in the skeleton"""

    this_frame_rotated_skeleton = np.zeros(
        this_frame_aligned_skeleton_data.shape
    )  # initialize the array to hold the rotated skeleton data for this frame
    num_tracked_points = this_frame_aligned_skeleton_data.shape[0]

    for i in range(num_tracked_points):
        this_frame_rotated_skeleton[i, :] = rotate_point(
            this_frame_aligned_skeleton_data[i, :], rotation_matrix
        )

    return this_frame_rotated_skeleton


# %%


def rotate_skeleton_to_vector(
    reference_vector: np.ndarray,
    vector_to_rotate_to: np.ndarray,
    original_skeleton_np_array: np.ndarray,
) -> np.ndarray:
    """
    Find the rotation matrix needed to rotate the 'reference vector' to match the 'vector_to_rotate_to', and
    rotate the entire skeleton with that matrix.

        Input:
            Reference Vector: The vector on the skeleton that you want to rotate/base the rotation matrix on
            Vector_to_rotate_to: The vector that you want to align the skeleton too (i.e. the x-axis/y-axis etc.)
            Original skeleton data: The freemocap data you want to rotate
        Output:
            rotated_skeleton_data: A numpy data array of your rotated skeleton

    """

    num_frames = original_skeleton_np_array.shape[0]
    reference_unit_vector = calculate_unit_vector(reference_vector)
    rotation_matrix = calculate_rotation_matrix(
        reference_unit_vector, vector_to_rotate_to
    )

    rotated_skeleton_data_array = np.zeros(original_skeleton_np_array.shape)
    for frame in track(range(num_frames), description="Rotating Skeleton"):
        rotated_skeleton_data_array[frame, :, :] = rotate_skeleton_frame(
            original_skeleton_np_array[frame, :, :], rotation_matrix
        )

    return rotated_skeleton_data_array


# %%


def align_skeleton_with_origin(
    skeleton_data: np.ndarray, skeleton_indices: list, good_frame: int
) -> tuple:
    """
    Takes in freemocap skeleton data and translates the skeleton to the origin, and then rotates the data
    so that the skeleton is facing the +y direction and standing in the +z direction

    Input:
        skeleton data: a 3D numpy array of skeleton data in freemocap format
        skeleton indices: a list of joints being tracked by mediapipe/your 2d pose estimator
        good frame: the frame that you want to base the rotation on (can be entered manually,
                    or use the 'good_frame_finder.py' to calculate it)
        debug: If 'True', display a plot of the raw data and the 3 main alignment stages

    Output:
        spine aligned skeleton data: a 3d numpy array of the origin aligned data in freemocap format
    """
    left_shoulder_index = skeleton_indices.index("left_shoulder")
    right_shoulder_index = skeleton_indices.index("right_shoulder")

    left_hip_index = skeleton_indices.index("left_hip")
    right_hip_index = skeleton_indices.index("right_hip")

    left_heel_index = skeleton_indices.index("left_heel")
    right_heel_index = skeleton_indices.index("right_heel")

    origin = np.array([0, 0, 0])
    x_axis = np.array([1, 0, 0])
    y_axis = np.array([0, 1, 0])
    z_axis = np.array([0, 0, 1])

    x_vector = create_vector(origin, x_axis)
    y_vector = create_vector(origin, y_axis)
    z_vector = create_vector(origin, z_axis)

    ## Translate the data such that the midpoint between the two feet is at the origin
    hip_translated_mid_foot_XYZ = calculate_mid_foot_XYZ_coordinate(
        skeleton_data[good_frame, :, :], left_heel_index, right_heel_index
    )
    foot_translated_skeleton_data = translate_skeleton_to_origin(
        hip_translated_mid_foot_XYZ, skeleton_data
    )

    # Rotate the skeleton to face the +y direction
    heel_vector_origin = foot_translated_skeleton_data[good_frame, right_heel_index, :]
    heel_vector = create_vector(
        heel_vector_origin,
        foot_translated_skeleton_data[good_frame, left_heel_index, :],
    )

    y_aligned_skeleton_data = rotate_skeleton_to_vector(
        heel_vector, -1 * x_vector, foot_translated_skeleton_data
    )

    # Rotating the skeleton so that the spine is aligned with +z
    y_aligned_mid_hip_XYZ = calculate_mid_hip_XYZ_coordinates(
        y_aligned_skeleton_data[good_frame, :, :], left_hip_index, right_hip_index
    )
    y_aligned_mid_shoulder_XYZ = calculate_shoulder_center_XYZ_coordinates(
        y_aligned_skeleton_data[good_frame, :, :],
        left_shoulder_index,
        right_shoulder_index,
    )
    y_aligned_spine_vector = create_vector(
        y_aligned_mid_hip_XYZ, y_aligned_mid_shoulder_XYZ
    )

    spine_aligned_skeleton_data = rotate_skeleton_to_vector(
        y_aligned_spine_vector, z_vector, y_aligned_skeleton_data
    )

    return (
        spine_aligned_skeleton_data,
        y_aligned_skeleton_data,
        foot_translated_skeleton_data,
    )


# %%
mediapipe_indices = [
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


# %%
def slice_mediapipe_data(mediapipe_full_skeleton_data, num_pose_joints):
    pose_joint_range = range(num_pose_joints)

    mediapipe_pose_data = mediapipe_full_skeleton_data[
        :, 0:num_pose_joints, :
    ]  # load just the pose joints into a data array, removing hands and face data

    return mediapipe_pose_data


# %%


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


def build_virtual_trunk_marker(
    freemocap_data, list_of_indices, trunk_joint_connection, frame
):
    trunk_marker_indices = return_indices_of_joints(
        list_of_indices, trunk_joint_connection
    )

    trunk_XYZ_coordinates = return_XYZ_coordinates_of_markers(
        freemocap_data, trunk_marker_indices, frame
    )

    trunk_proximal = (trunk_XYZ_coordinates[0] + trunk_XYZ_coordinates[1]) / 2
    trunk_distal = (trunk_XYZ_coordinates[2] + trunk_XYZ_coordinates[3]) / 2

    return trunk_proximal, trunk_distal


# %%


def build_mediapipe_skeleton(
    mediapipe_pose_data, segment_dataframe, mediapipe_indices
) -> list:
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

    mediapipe_frame_segment_joint_XYZ = (
        []
    )  # empty list to hold all the skeleton XYZ coordinates/frame

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

                # based on index, excract coordinate data from fmc mediapipe data
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

                proximal_joint_foot_index = mediapipe_indices.index(
                    proximal_joint_foot_name
                )

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
        f = 2

    return mediapipe_frame_segment_joint_XYZ


# %%
# values for segment weight and segment mass percentages taken from Winter anthropometry tables
# https://imgur.com/a/aD74j
# Winter, D.A. (2005) Biomechanics and Motor Control of Human Movement. 3rd Edition, John Wiley & Sons, Inc., Hoboken.


segments = [
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
    for frame in track(
        num_frame_range, description="Calculating Segment Center of Mass"
    ):
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
    segment_COM_frame_imgPoint_XYZ = np.empty(
        [int(len(num_frame_range)), int(num_segments), 3]
    )
    for frame in num_frame_range:
        this_frame_skeleton = segment_COM_frame_dict[frame]
        for joint_count, segment in enumerate(this_frame_skeleton.keys()):
            segment_COM_frame_imgPoint_XYZ[frame, joint_count, :] = this_frame_skeleton[
                segment
            ]
    return segment_COM_frame_imgPoint_XYZ


# %%


def calculate_total_body_COM(
    segment_conn_len_perc_dataframe, segment_COM_frame_dict, num_frame_range
):
    totalBodyCOM_frame_XYZ = np.empty([int(len(num_frame_range)), 3])

    for frame in track(
        num_frame_range, description="Calculating Total Body Center of Mass"
    ):

        this_frame_total_body_percentages = []
        this_frame_skeleton = segment_COM_frame_dict[frame]

        for segment, segment_info in segment_conn_len_perc_dataframe.iterrows():
            this_segment_COM = this_frame_skeleton[segment]
            this_segment_COM_percentage = segment_info["Segment_COM_Percentage"]

            this_segment_total_body_percentage = (
                this_segment_COM * this_segment_COM_percentage
            )
            this_frame_total_body_percentages.append(this_segment_total_body_percentage)

        this_frame_total_body_COM = np.nansum(this_frame_total_body_percentages, axis=0)

        totalBodyCOM_frame_XYZ[frame, :] = this_frame_total_body_COM

    f = 2
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


def run(
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
    segment_COM_frame_imgPoint_XYZ = reformat_segment_COM(
        segment_COM_frame_dict, num_frame_range, num_segments
    )
    totalBodyCOM_frame_XYZ = calculate_total_body_COM(
        anthropometric_info_dataframe, segment_COM_frame_dict, num_frame_range
    )

    return (
        segment_COM_frame_dict,
        segment_COM_frame_imgPoint_XYZ,
        totalBodyCOM_frame_XYZ,
    )


# %%
def gap_fill_filter_origin_align_3d_data_and_then_calculate_center_of_mass(
    skel3d_frame_marker_xyz: np.ndarray,
    data_arrays_path: [str, Path],
    # Filter the data, set the filtering options here
    sampling_rate: Union[float, int],
    cut_off: Union[float, int],
    order: Union[float, int],
    reference_frame_number: Union[float, int] = None,
):
    # Interpolate the data
    freemocap_interpolated_data = interpolate_freemocap_data(skel3d_frame_marker_xyz)

    # Filter the data
    freemocap_filtered_marker_data = filter_skeleton(
        freemocap_interpolated_data, cut_off, sampling_rate, order
    )
    np.save(
        data_arrays_path / "mediaPipeSkel_3d_filtered", freemocap_filtered_marker_data
    )

    # add the good frame finder

    # Align the data
    if reference_frame_number is None:
        reference_frame_number = 0
        # print("Finding good frame to align data with origin ")
        # reference_frame_number = find_good_frame(
        #     freemocap_filtered_marker_data, mediapipe_indices, 0.3
        # )

    freemocap_alignment_marker_data_tuple = align_skeleton_with_origin(
        freemocap_filtered_marker_data, mediapipe_indices, reference_frame_number
    )
    origin_aligned_freemocap_marker_data = freemocap_alignment_marker_data_tuple[0]
    logger.info("Saving Origin Aligned Data")
    np.save(
        data_arrays_path / "mediaPipeSkel_3d_origin_aligned",
        origin_aligned_freemocap_marker_data,
    )

    # Calculate segment and total body COM
    print("Calculating COM")
    anthropometric_info_dataframe = build_anthropometric_dataframe(
        segments, joint_connections, segment_COM_lengths, segment_COM_percentages
    )
    skelcoordinates_frame_segment_joint_XYZ = build_mediapipe_skeleton(
        origin_aligned_freemocap_marker_data,
        anthropometric_info_dataframe,
        mediapipe_indices,
    )
    (
        segment_COM_frame_dict,
        segment_COM_frame_imgPoint_XYZ,
        totalBodyCOM_frame_XYZ,
    ) = run(
        origin_aligned_freemocap_marker_data,
        skelcoordinates_frame_segment_joint_XYZ,
        anthropometric_info_dataframe,
    )

    np.save(
        data_arrays_path / "segmentedCOM_frame_joint_XYZ.npy",
        segment_COM_frame_imgPoint_XYZ,
    )
    np.save(data_arrays_path / "totalBodyCOM_frame_XYZ.npy", totalBodyCOM_frame_XYZ)
    open_file = open(data_arrays_path / "mediapipe_skeleton_segments_dict.pkl", "wb")
    pickle.dump(skelcoordinates_frame_segment_joint_XYZ, open_file)
    open_file.close()
    # Save filtered data here
