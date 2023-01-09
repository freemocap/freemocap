import logging
from pathlib import Path
from typing import Union

from old_src.core_processes.batch_processing.process_session_folder import (
    process_session_folder,
)
from old_src.core_processes.batch_processing.session_processing_parameter_models import (
    SessionProcessingParameterModel,
)
from old_src.core_processes.capture_volume_calibration.anipose_camera_calibration import (
    freemocap_anipose,
)
from rich.pretty import pprint

logger = logging.getLogger(__name__)


def batch_process_session_folders(
    path_to_folder_of_session_folders: Union[str, Path],
    path_to_camera_calibration_toml: Union[str, Path],
    path_to_blender_executable: Union[str, Path],
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
        Path to a Blender executable.

    """

    for session_folder_path in Path(path_to_folder_of_session_folders).iterdir():
        if not session_folder_path.is_dir():
            continue

        logger.info(f"Processing session folder: {session_folder_path}")
        if Path(
            session_folder_path / "synchronized_videos"
        ).exists():  # session was recorded freemocap version > v0.0.54 (aka `alpha`)
            synchronized_videos_folder = (
                Path(session_folder_path) / "synchronized_videos"
            )

        if Path(
            session_folder_path / "SyncedVideos"
        ).exists():  # session was recorded with freemocap version <= v0.0.54 (aka `pre-alpha`)
            synchronized_videos_folder = Path(session_folder_path) / "SyncedVideos"
        else:
            print(
                f"No folder full of synchronized videos found for {session_folder_path}"
            )
            raise FileNotFoundError

        anipose_calibration_object = freemocap_anipose.CameraGroup.load(
            str(path_to_camera_calibration_toml)
        )

        output_data_folder = Path(session_folder_path) / "output_data"
        output_data_folder.mkdir(exist_ok=True, parents=True)

        session_processing_parameter_model = SessionProcessingParameterModel(
            path_to_session_folder=session_folder_path,
            path_to_output_data_folder=output_data_folder,
            path_to_folder_of_synchronized_videos=synchronized_videos_folder,
            anipose_calibration_object=anipose_calibration_object,
            path_to_blender_executable=path_to_blender_executable,
        )

        session_processing_parameter_model.anipose_triangulate_3d_parameters_model.use_triangulate_ransac_method = (
            False
        )

        session_processing_parameter_model.start_processing_at_stage = 0

        pprint(session_processing_parameter_model.dict(), expand_all=True)

        process_session_folder(session_processing_parameter_model)


if __name__ == "__main__":

    path_to_folder_of_session_folders = Path(
        r"H:\My Drive\Biol2299_Fall2022\partially_processed\FreeMocap_Data"
    )
    # path_to_folder_of_session_folders = Path(
    #     r"H:\My Drive\Biol2299_Fall2022\done_needs_checking"
    # )

    path_to_camera_calibration_toml = Path(
        r"H:\My Drive\Biol2299_Fall2022\calibration_recordings\sesh_2022-09-28_15_57_08_calibration\sesh_2022-09-28_15_57_08_calibration_calibration.toml"
    )

    path_to_blender_executable = Path(
        r"C:\Program Files\Blender Foundation\Blender 3.2\blender.exe"
    )

    batch_process_session_folders(
        path_to_folder_of_session_folders=path_to_folder_of_session_folders,
        path_to_camera_calibration_toml=path_to_camera_calibration_toml,
        path_to_blender_executable=path_to_blender_executable,
    )
