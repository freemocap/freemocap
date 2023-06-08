import json
from pathlib import Path
from typing import Union


def load_dataframes(recording_folder_path: Union[str, Path]):
    output_folder_path = Path(recording_folder_path) / "output_data"

    with open(output_folder_path / "mediapipe_names_and_connections_dict.json", 'r') as file:
        json_data = file.read()
    names_and_connections = json.loads(json_data)

    with open(output_folder_path / "mediapipe_skeleton_segment_lengths.json", 'r') as file:
        json_data = file.read()
    segment_lengths = json.loads(json_data)

    return {
        "body": pd.read_csv(output_folder_path / "mediapipe_body_3d_xyz.csv"),
        "hands": {"right": pd.read_csv(output_folder_path / "mediapipe_right_hand_3d_xyz.csv"),
                  "left": pd.read_csv(output_folder_path / "mediapipe_left_hand_3d_xyz.csv")},
        "face": pd.read_csv(output_folder_path / "mediapipe_face_3d_xyz.csv"),
        "center_of_mass": pd.read_csv(output_folder_path / "total_body_center_of_mass.csv"),
        "names_and_connections": names_and_connections,
        "segment_lengths": segment_lengths,
    }
