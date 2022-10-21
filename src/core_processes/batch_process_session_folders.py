from pathlib import Path
from typing import Union

import pandas as pd

from src.blender_stuff.create_blend_file_from_session_data import (
    create_blend_file_from_session_data,
)
from src.core_processes.capture_volume_calibration.anipose_camera_calibration import (
    freemocap_anipose,
)
from src.core_processes.capture_volume_calibration.triangulate_3d_data import (
    triangulate_3d_data,
)
from src.core_processes.mediapipe_stuff.convert_mediapipe_npy_to_csv import (
    convert_mediapipe_npy_to_csv,
)
from src.core_processes.mediapipe_stuff.mediapipe_skeleton_detector import (
    MediaPipeSkeletonDetector,
)
from src.core_processes.post_process_skeleton_data.estimate_skeleton_segment_lengths import (
    estimate_skeleton_segment_lengths,
    mediapipe_skeleton_segment_definitions,
    save_skeleton_segment_lengths_to_json,
)
from src.core_processes.post_process_skeleton_data.gap_fill_filter_and_origin_align_skeleton_data import (
    gap_fill_filter_origin_align_3d_data_and_then_calculate_center_of_mass,
)


def process_session_folder(
    synchronized_videos_folder: Union[str, Path],
    output_data_folder: Union[str, Path],
):
    if not synchronized_videos_folder.exists():
        raise FileNotFoundError(
            f"Could not find synchronized_videos folder at {synchronized_videos_folder}"
        )

    print("Detecting 2d skeletons...")
    # 2d skeleton detection
    # TODO - this doesn't need to be a class - make it a function
    mediapipe_skeleton_detector = MediaPipeSkeletonDetector()
    mediapipe_2d_data = mediapipe_skeleton_detector.process_folder_full_of_videos(
        synchronized_videos_folder, output_data_folder
    )

    print("Triangulating 3d skeletons...")
    # 3d skeleton triangulation
    skel3d_frame_marker_xyz, skeleton_reprojection_error_fr_mar = triangulate_3d_data(
        anipose_calibration_object=anipose_calibration_object,
        mediapipe_2d_data=mediapipe_2d_data,
        output_data_folder_path=output_data_folder,
        mediapipe_confidence_cutoff_threshold=0.7,
        use_triangulate_ransac=True,
    )

    print(
        "Gap-filling, butterworth filtering, origin aligning 3d skeletons, then calculating center of mass ..."
    )
    # Post Process raw data
    gap_fill_filter_origin_align_3d_data_and_then_calculate_center_of_mass(
        skel3d_frame_marker_xyz,
        skeleton_reprojection_error_fr_mar=skeleton_reprojection_error_fr_mar,
        data_arrays_path=output_data_folder,
        sampling_rate=30,
        cut_off=10,
        order=4,
        reference_frame_number=None,
    )

    print("Breaking up big `npy` into smaller bits and converting to `csv`...")
    # break up big NPY and save out csv's
    convert_mediapipe_npy_to_csv(
        mediapipe_3d_frame_trackedPoint_xyz=skel3d_frame_marker_xyz,
        output_data_folder_path=output_data_folder,
    )

    print("Creating Blender animation from motion capture data...")
    # export to Blender
    path_to_skeleton_body_csv = output_data_folder / "mediapipe_body_3d_xyz.csv"
    skeleton_dataframe = pd.read_csv(path_to_skeleton_body_csv)

    skeleton_segment_lengths_dict = estimate_skeleton_segment_lengths(
        skeleton_dataframe=skeleton_dataframe,
        skeleton_segment_definitions=mediapipe_skeleton_segment_definitions,
    )

    save_skeleton_segment_lengths_to_json(
        output_data_folder, skeleton_segment_lengths_dict
    )
    create_blend_file_from_session_data(
        session_folder_path=Path(synchronized_videos_folder).parent,
        blender_exe_path=path_to_blender_executable,
    )


if __name__ == "__main__":

    path_to_folder_of_session_folders = Path(
        r"D:\Dropbox\Northeastern\Courses\Biol2299\2022_09_Fall\freemocap_bos_com_standing_data\FreeMocap_Data"
    )

    path_to_camera_calibration_toml = Path(
        r"D:\Dropbox\Northeastern\Courses\Biol2299\2022_09_Fall\freemocap_bos_com_standing_data\FreeMocap_Data\sesh_2022-09-28_15_57_08_calibration\sesh_2022-09-28_15_57_08_calibration_calibration.toml"
    )

    path_to_blender_executable = Path(
        r"C:\Program Files\Blender Foundation\Blender 3.2\blender.exe"
    )

    anipose_calibration_object = freemocap_anipose.CameraGroup.load(
        str(path_to_camera_calibration_toml)
    )

    # get paths to folder full of session folders
    list_of_session_folders = list(path_to_folder_of_session_folders.glob("ses*"))
    print(list_of_session_folders)

    # %%
    session_type = "pre-alpha"
    for session_folder in list_of_session_folders:
        print(f"Processing {session_folder}")
        if session_type == "pre-alpha":
            synchronized_videos_folder = Path(session_folder) / "SyncedVideos"
        else:
            synchronized_videos_folder = Path(session_folder) / "synchronized_videos"

        output_data_folder = Path(session_folder) / "output_data"
        output_data_folder.mkdir(exist_ok=True, parents=True)
        process_session_folder(
            synchronized_videos_folder=synchronized_videos_folder,
            output_data_folder=output_data_folder,
        )

    print("Done!")
