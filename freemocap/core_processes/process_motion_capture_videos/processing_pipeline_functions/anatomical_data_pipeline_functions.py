import logging
from pathlib import Path
from typing import Dict
import numpy as np
import pandas as pd

from freemocap.core_processes.post_process_skeleton_data.estimate_skeleton_segment_lengths import (
    estimate_skeleton_segment_lengths,
    mediapipe_skeleton_segment_definitions,
)
from freemocap.core_processes.post_process_skeleton_data.calculate_center_of_mass import run_center_of_mass_calculations
from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel
from freemocap.system.paths_and_filenames.file_and_folder_names import MEDIAPIPE_BODY_3D_DATAFRAME_CSV_FILE_NAME

logger = logging.getLogger(__name__)


def calculate_anatomical_data(
    processing_parameters: ProcessingParameterModel,
    skel3d_frame_marker_xyz: np.ndarray,
) -> Dict[str, np.ndarray]:
    logger.info("Calculating center of mass...")
    segment_COM_frame_imgPoint_XYZ, totalBodyCOM_frame_XYZ = run_center_of_mass_calculations(
        processed_skel3d_frame_marker_xyz=skel3d_frame_marker_xyz
    )

    path_to_skeleton_body_csv = (
        Path(processing_parameters.recording_info_model.output_data_folder_path)
        / MEDIAPIPE_BODY_3D_DATAFRAME_CSV_FILE_NAME
    )
    skeleton_dataframe = pd.read_csv(path_to_skeleton_body_csv)

    logger.info("Estimating skeleton segment lengths...")
    skeleton_segment_lengths_dict = estimate_skeleton_segment_lengths(
        skeleton_dataframe=skeleton_dataframe,
        skeleton_segment_definitions=mediapipe_skeleton_segment_definitions,
    )

    return {
        "segment_COM": segment_COM_frame_imgPoint_XYZ,
        "total_body_COM": totalBodyCOM_frame_XYZ,
        "skeleton_segment_lengths": skeleton_segment_lengths_dict,
    }
