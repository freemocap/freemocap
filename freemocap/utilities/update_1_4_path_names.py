from typing import Optional, Union
from pathlib import Path


from freemocap.system.paths_and_filenames.file_and_folder_names import (
    RAW_DATA_FOLDER_NAME,
    OUTPUT_DATA_FOLDER_NAME,
    CENTER_OF_MASS_FOLDER_NAME,
    RECORDING_SESSIONS_FOLDER_NAME,
)
from freemocap.system.paths_and_filenames.path_getters import get_freemocap_data_folder_path


def update_1_4_path_names(freemocap_data_folder_path: Optional[Union[str, Path]]) -> None:
    if freemocap_data_folder_path is None:
        freemocap_data_folder_path = get_freemocap_data_folder_path()

    print(f"Searching for recording folders in {freemocap_data_folder_path}")

    for session_folder in (Path(freemocap_data_folder_path) / RECORDING_SESSIONS_FOLDER_NAME).iterdir():
        if not session_folder.is_dir():
            continue

        for recording_folder in session_folder.iterdir():
            if not recording_folder.is_dir():
                continue

            update_recording_folder(recording_folder)


def update_recording_folder(recording_folder: Path) -> None:
    if (
        recording_folder.name == OUTPUT_DATA_FOLDER_NAME
    ):  # this covers cases where the recording folder isn't a subfolder of a session
        rename_skeleton_file_path(recording_folder)
        if (recording_folder / RAW_DATA_FOLDER_NAME).exists():
            rename_raw_data_paths(recording_folder / RAW_DATA_FOLDER_NAME)
        if (recording_folder / CENTER_OF_MASS_FOLDER_NAME).exists():
            rename_COM_paths(recording_folder / CENTER_OF_MASS_FOLDER_NAME)
    elif (recording_folder / OUTPUT_DATA_FOLDER_NAME).exists():
        rename_skeleton_file_path(recording_folder)
        if (recording_folder / OUTPUT_DATA_FOLDER_NAME / RAW_DATA_FOLDER_NAME).exists():
            rename_raw_data_paths(recording_folder / OUTPUT_DATA_FOLDER_NAME / RAW_DATA_FOLDER_NAME)
        if (recording_folder / OUTPUT_DATA_FOLDER_NAME / CENTER_OF_MASS_FOLDER_NAME).exists():
            rename_COM_paths(recording_folder / OUTPUT_DATA_FOLDER_NAME / CENTER_OF_MASS_FOLDER_NAME)


def rename_raw_data_paths(raw_data_folder_path: Path) -> None:
    print(f"renaming raw data files in {raw_data_folder_path}")
    for file in raw_data_folder_path.iterdir():
        if file.name == "mediapipe2dData_numCams_numFrames_numTrackedPoints_pixelXY.npy":
            file.rename(file.parent / "mediapipe_2dData_numCams_numFrames_numTrackedPoints_pixelXY.npy")
        elif file.name == "mediapipe3dData_numCams_numFrames_numTrackedPoints_reprojectionError.npy":
            file.rename(file.parent / "mediapipe_3dData_numCams_numFrames_numTrackedPoints_reprojectionError.npy")
        elif file.name == "mediapipe3dData_numFrames_numTrackedPoints_reprojectionError.npy":
            file.rename(file.parent / "mediapipe_3dData_numFrames_numTrackedPoints_reprojectionError.npy")
        elif file.name == "mediapipe3dData_numFrames_numTrackedPoints_spatialXYZ.npy":
            file.rename(file.parent / "mediapipe_3dData_numFrames_numTrackedPoints_spatialXYZ.npy")

    print(f"successfully renamed raw data files in {raw_data_folder_path}")


def rename_skeleton_file_path(output_data_folder_path: Path) -> None:
    print(f"renaming skeleton 3D files in {output_data_folder_path}")
    for file in output_data_folder_path.iterdir():
        if file.name == "mediaPipeSkel_3d_body_hands_face.npy":
            file.rename(file.parent / "mediapipe_skeleton_3d.npy")

    print(f"successfully renamed skeleton 3D files in {output_data_folder_path}")


def rename_COM_paths(COM_data_folder_path: Path) -> None:
    print(f"renaming center of mass files in {COM_data_folder_path}")

    for file in COM_data_folder_path.iterdir():
        if file.name == "segmentCOM_frame_joint_xyz.npy":
            file.rename(file.parent / "mediapipe_segmentCOM_frame_joint_xyz.npy")
        elif file.name == "total_body_center_of_mass_xyz.npy":
            file.rename(file.parent / "mediapipe_total_body_center_of_mass_xyz.npy")

    print(f"successfully renamed center of mass files in {COM_data_folder_path}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        update_1_4_path_names(Path(sys.argv[1]))
    else:
        update_1_4_path_names(None)
