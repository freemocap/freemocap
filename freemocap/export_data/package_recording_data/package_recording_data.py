import json
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from freemocap.core_processes.post_process_skeleton_data.gap_fill_filter_and_origin_align_skeleton_data import \
    BODY_SEGMENT_NAMES
from freemocap.system.paths_and_filenames.path_getters import get_output_data_folder_path, \
    get_total_body_center_of_mass_file_path, get_segment_center_of_mass_file_path


def save_data_by_frame_number(recording_folder_path: Union[Path, str], include_hands:bool=True, include_face:bool=True):
    output_folder_path = Path(get_output_data_folder_path(recording_folder_path))
    body_df = pd.read_csv(output_folder_path / "mediapipe_body_3d_xyz.csv")
    right_hand_df = pd.read_csv(output_folder_path / "mediapipe_right_hand_3d_xyz.csv")
    left_hand_df = pd.read_csv(output_folder_path / "mediapipe_left_hand_3d_xyz.csv")
    face_df = pd.read_csv(output_folder_path / "mediapipe_face_3d_xyz.csv")

    center_of_mass_xyz  = np.load(get_total_body_center_of_mass_file_path(output_data_folder = output_folder_path))
    center_of_mass_df = pd.DataFrame(center_of_mass_xyz, columns=["x", "y", "z"])

    segment_center_of_mass_segment_xyz = np.load(get_segment_center_of_mass_file_path(output_data_folder = output_folder_path))
    segment_center_column_names = []
    segment_center_flat = segment_center_of_mass_segment_xyz.flatten()
    for segment_name in BODY_SEGMENT_NAMES:
        for dimension in ["x", "y", "z"]:
            segment_center_column_names.append(f"{segment_name}_{dimension}")
    segment_center_of_mass_df = pd.DataFrame(segment_center_flat, columns=segment_center_column_names)

    if not (len(body_df) == len(right_hand_df) == len(left_hand_df) == len(face_df)):
        raise ValueError("All dataframes must have the same number of rows (i.e. frames)")

    number_of_frames = len(body_df)

    with open(output_folder_path / "mediapipe_names_and_connections_dict.json", 'r') as file:
        json_data = file.read()
    names_and_connections = json.loads(json_data)

    with open(output_folder_path / "mediapipe_skeleton_segment_lengths.json", 'r') as file:
        json_data = file.read()
    segment_lengths = json.loads(json_data)


    data_by_frame_number = {}

    for frame_number in range(number_of_frames):

        body_data = body_df[frame_number]
        right_hand_data = right_hand_df[frame_number]
        left_hand_data = left_hand_df[frame_number]
        face_data = face_df[frame_number]

        data_by_frame_number[frame_number] = {}

        for column_name in body_df.columns:
            parts = column_name.split('_')
            point_name = parts[0]  # e.g. "nose"
            dimension = parts[1]  # x, y, or z
            if point_name not in data_by_frame_number[frame_number]:
                data_by_frame_number[frame_number][point_name] = {}
            data_by_frame_number[frame_number]["body"][point_name][dimension] = body_data[column_name]

        if include_hands:
            for column_name in right_hand_df.columns:
                parts = column_name.split('_')
                point_name = parts[0]
                dimension = parts[1]
                if point_name not in data_by_frame_number[frame_number]:
                    data_by_frame_number[frame_number][point_name] = {}
                data_by_frame_number[frame_number]["hands"]["right"][point_name][dimension] = right_hand_data[column_name]

            for column_name in left_hand_df.columns:
                parts = column_name.split('_')
                point_name = parts[0]
                dimension = parts[1]
                if point_name not in data_by_frame_number[frame_number]:
                    data_by_frame_number[frame_number][point_name] = {}
                data_by_frame_number[frame_number]["hands"]["left"][point_name][dimension] = left_hand_data[
                    column_name]

        if include_face:
            for column_name in face_df.columns:
                parts = column_name.split('_')
                point_name = parts[0]
                dimension = parts[1]
                if point_name not in data_by_frame_number[frame_number]:
                    data_by_frame_number[frame_number][point_name] = {}
                data_by_frame_number[frame_number]["face"][point_name][dimension] = face_data[
                    column_name]

    return data_by_frame_number

