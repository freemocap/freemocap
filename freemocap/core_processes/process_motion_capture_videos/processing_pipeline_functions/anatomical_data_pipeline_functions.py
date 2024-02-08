import logging
import multiprocessing
from pathlib import Path
from typing import Dict
import numpy as np
import pandas as pd
from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.convert_mediapipe_npy_to_csv import (
    convert_mediapipe_npy_to_csv,
)

from freemocap.core_processes.post_process_skeleton_data.estimate_skeleton_segment_lengths import (
    estimate_skeleton_segment_lengths,
    mediapipe_skeleton_segment_definitions,
)
from freemocap.core_processes.post_process_skeleton_data.calculate_center_of_mass import run_center_of_mass_calculations
from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel
from freemocap.system.logging.queue_logger import DirectQueueHandler
from freemocap.system.paths_and_filenames.file_and_folder_names import MEDIAPIPE_BODY_3D_DATAFRAME_CSV_FILE_NAME
from freemocap.system.logging.configure_logging import log_view_logging_format_string

logger = logging.getLogger(__name__)


def calculate_anatomical_data(
    processing_parameters: ProcessingParameterModel,
    skel3d_frame_marker_xyz: np.ndarray,
    queue: multiprocessing.Queue,
) -> Dict[str, np.ndarray]:
    if queue:
        handler = DirectQueueHandler(queue)
        handler.setFormatter(logging.Formatter(fmt=log_view_logging_format_string, datefmt="%Y-%m-%dT%H:%M:%S"))
        logger.addHandler(handler)

    # TODO: start this by building skeleton dictionary we use in both COM and segment lengths

    logger.info("Calculating center of mass...")
    try:
        segment_COM_frame_imgPoint_XYZ, totalBodyCOM_frame_XYZ = run_center_of_mass_calculations(
            processed_skel3d_frame_marker_xyz=skel3d_frame_marker_xyz,
            tracking_model_info=processing_parameters.tracking_model_info,
        )
    except ValueError:
        logger.warning("Center of mass cannot be calculated for this tracking model")
        segment_COM_frame_imgPoint_XYZ = totalBodyCOM_frame_XYZ = None

    convert_mediapipe_npy_to_csv(
        mediapipe_3d_frame_trackedPoint_xyz=skel3d_frame_marker_xyz,
        output_data_folder_path=processing_parameters.recording_info_model.output_data_folder_path,
    )  # TODO: separate functionality of splitting into CSVs and savings to disk

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
