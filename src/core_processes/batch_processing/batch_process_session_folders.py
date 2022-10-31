from pathlib import Path
from typing import Union, Any, Dict


def batch_process_session_folders(
    path_to_folder_of_session_folders: Union[str, Path],
    path_to_camera_calibration_toml: Union[str, Path],
    path_to_blender_executable: Union[str, Path],
    processing_dictionary: Dict[str, Dict[str, Any]],
):
    """
    Process a folder full of session folders.

    Parameters
    ----------
    path_to_folder_of_session_folders : Union[str, Path]
        Path to folder full of session folders.
    path_to_camera_calibration_toml : Union[str, Path]
        Path to camera calibration toml file.
    path_to_blender_executable : Union[str, Path]
        Path to Blender executable.
    processing_dictionary : Dict[str, Dict[str, Any]]
        Dictionary of processing steps to perform on each session folder.



    """
    for session_folder in Path(path_to_folder_of_session_folders).iterdir():
        if session_folder.is_dir():
            process_session_folder(
                session_folder_path=session_folder,
                path_to_camera_calibration_toml=path_to_camera_calibration_toml,
                path_to_blender_executable=path_to_blender_executable,
                processing_dictionary=processing_dictionary,
            )

    return None
