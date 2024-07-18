from typing import Optional, Union
from pathlib import Path


from freemocap.system.paths_and_filenames.file_and_folder_names import (
    RAW_DATA_FOLDER_NAME,
    OUTPUT_DATA_FOLDER_NAME,
    RECORDING_SESSIONS_FOLDER_NAME,
)
from freemocap.system.paths_and_filenames.path_getters import get_freemocap_data_folder_path


def update_raw_data_paths(freemocap_data_folder_path: Optional[Union[str, Path]]) -> None:
    if freemocap_data_folder_path is None:
        freemocap_data_folder_path = get_freemocap_data_folder_path()

    print(f"Searching for raw data folders in {freemocap_data_folder_path}")

    for session_folder in (Path(freemocap_data_folder_path) / RECORDING_SESSIONS_FOLDER_NAME).iterdir():
        if not session_folder.is_dir():
            continue

        for recording_folder in session_folder.iterdir():
            if not recording_folder.is_dir():
                continue

            if recording_folder.name == OUTPUT_DATA_FOLDER_NAME:
                if (recording_folder / RAW_DATA_FOLDER_NAME).exists():
                    rename_raw_data_paths(recording_folder / RAW_DATA_FOLDER_NAME)
            elif (recording_folder / OUTPUT_DATA_FOLDER_NAME / RAW_DATA_FOLDER_NAME).exists():
                rename_raw_data_paths(recording_folder / OUTPUT_DATA_FOLDER_NAME / RAW_DATA_FOLDER_NAME)
            else:
                continue


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


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        update_raw_data_paths(Path(sys.argv[1]))
    else:
        update_raw_data_paths(None)