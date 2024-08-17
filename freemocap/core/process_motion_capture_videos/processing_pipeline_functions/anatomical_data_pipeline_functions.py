import logging
import multiprocessing
from typing import Dict
import numpy as np
from freemocap.core.detecting_things_in_2d_images.mediapipe_stuff.convert_mediapipe_npy_to_csv import (
    convert_mediapipe_npy_to_csv,
)
from freemocap.core.post_process_skeleton_data.calculate_center_of_mass import run_center_of_mass_calculations
from freemocap.data.recording_models.post_processing_parameter_models import ProcessingParameterModel
from freemocap.system.logging.queue_logger import DirectQueueHandler
from freemocap.system.logging.configure_logging import log_view_logging_format_string

logger = logging.getLogger(__name__)


def calculate_anatomical_data(
    processing_parameters: ProcessingParameterModel,
    skel3d_frame_marker_xyz: np.ndarray,
) -> Dict[str, np.ndarray]:


    logger.info("Calculating center of mass...")
    segment_COM_frame_imgPoint_XYZ, totalBodyCOM_frame_XYZ = run_center_of_mass_calculations(
        processed_skel3d_frame_marker_xyz=skel3d_frame_marker_xyz
    )

    convert_mediapipe_npy_to_csv(
        mediapipe_3d_frame_trackedPoint_xyz=skel3d_frame_marker_xyz,
        output_data_folder_path=processing_parameters.recording_info_model.output_data_folder_path,
    )  # TODO: separate functionality of splitting into CSVs and savings to disk

    return {
        "segment_COM": segment_COM_frame_imgPoint_XYZ,
        "total_body_COM": totalBodyCOM_frame_XYZ,
    }
