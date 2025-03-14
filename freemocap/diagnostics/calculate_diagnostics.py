import numpy as np 
from pathlib import Path
import pandas as pd
from tracker_info.model_info import ModelInfo, MediapipeModelInfo
from freemocap.diagnostics.run_test_data import get_sample_session_path




def load_and_slice_data(path_to_data:Path, slice_of_data:slice):
    data = np.load(path_to_data)
    return data, data[:, slice_of_data, :]

def calculate_jerk(position:np.ndarray): #NOTE: may want to divide by dt, but if we're just using this for comparison it may not be necessary. However if we do want dt, will either need timestamps or framerate as well
    velocity = np.diff(position, axis=0)
    acceleration = np.diff(velocity, axis=0)
    jerk = np.diff(acceleration, axis=0)

    return jerk

def calculate_jerk_statistics(jerk_3d_data:np.ndarray):
    total_mean_jerk = np.nanmean((np.abs(jerk_3d_data)))
    mean_jerk_per_joint = np.nanmean(np.abs(jerk_3d_data), axis = (0,2))

    return total_mean_jerk, mean_jerk_per_joint

def format_jerk_data_as_dataframe(
    total_mean_jerk: dict, 
    mean_jerk_per_joint: dict, 
    freemocap_version: str, 
    joint_names: list[str]
):
    """
    Formats jerk data into a structured DataFrame where the version is stored properly in each row.
    """
    # Store total jerk values
    total_jerk_rows = [
        {"version": freemocap_version, "data_stage": data_type, "name": "total", "mean_jerk": total_jerk_mean}
        for data_type, total_jerk_mean in total_mean_jerk.items()
    ]

    # Store per-joint jerk values
    joint_jerk_rows = [
        {"version": freemocap_version, "data_stage": data_type, "name": joint_name, "mean_jerk": jerk_value}
        for data_type, jerk_per_joint in mean_jerk_per_joint.items()
        for joint_name, jerk_value in zip(joint_names, jerk_per_joint)
    ]

    # Create the DataFrame
    df = pd.DataFrame(total_jerk_rows + joint_jerk_rows)

    return df


def run(path_to_recording:Path,
        model_info:ModelInfo,
        freemocap_version:str,
        ):

    path_to_raw_data = path_to_recording/'output_data'/'raw_data'/'mediapipe_3dData_numFrames_numTrackedPoints_spatialXYZ.npy'
    path_to_processed_data = path_to_recording/'output_data'/'mediapipe_skeleton_3d.npy'



    total_mean_jerk = {}
    mean_jerk_per_joint = {}

    raw_data, raw_body_data = load_and_slice_data(path_to_data= path_to_raw_data,
                                                slice_of_data = model_info.aspect_order_and_slices['body'] )

    processed_data, processed_body_data = load_and_slice_data(path_to_data=path_to_processed_data,
                                                            slice_of_data= model_info.aspect_order_and_slices['body'])


    raw_body_jerk = calculate_jerk(raw_body_data)
    raw_total_mean_body_jerk, raw_mean_jerk_per_joint = calculate_jerk_statistics(jerk_3d_data=raw_body_jerk)
    total_mean_jerk['raw'] = raw_total_mean_body_jerk
    mean_jerk_per_joint['raw'] = raw_mean_jerk_per_joint


    processed_body_jerk = calculate_jerk(processed_body_data)
    processed_total_mean_body_jerk, processed_mean_jerk_per_joint = calculate_jerk_statistics(jerk_3d_data=processed_body_jerk)
    total_mean_jerk['processed'] = processed_total_mean_body_jerk
    mean_jerk_per_joint['processed'] = processed_mean_jerk_per_joint


    df = format_jerk_data_as_dataframe(total_mean_jerk=total_mean_jerk,
                            mean_jerk_per_joint=mean_jerk_per_joint,
                            freemocap_version=freemocap_version,
                            joint_names = model_info.aspects['body'].tracked_points_names
                            )

    save_path = Path("freemocap/diagnostics/version_diagnostics") / f"recording_diagnostics_{freemocap_version}.csv"
    df.to_csv(save_path, index=False)
    print(f"Saved diagnostics to {save_path}")


if __name__ == "__main__":
    model_info = MediapipeModelInfo()
    # Use environment detection to handle different runners
    import os
    if os.name == 'nt':  # Windows
        path_to_recording = Path(r"C:\Users\runneradmin\freemocap_data\recording_sessions\freemocap_test_data")
    elif os.name == 'posix':
        path_to_recording = Path("/home/runner/freemocap_data/recording_sessions/freemocap_test_data")

    freemocap_version = 'current'
    run(path_to_recording=path_to_recording,
        model_info=model_info,
        freemocap_version=freemocap_version)

