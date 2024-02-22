import logging
import multiprocessing
from pathlib import Path
import numpy as np


from freemocap.core_processes.post_process_skeleton_data.post_process_skeleton import save_numpy_array_to_disk
from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel
from freemocap.system.logging.queue_logger import DirectQueueHandler
from freemocap.system.logging.configure_logging import log_view_logging_format_string
from freemocap.system.paths_and_filenames.file_and_folder_names import (
    CENTER_OF_MASS_FOLDER_NAME,
    SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME,
    TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME,
)
from freemocap.utilities.save_dictionary_to_json import save_dictionary_to_json


logger = logging.getLogger(__name__)


def save_data(
    skel3d_frame_marker_xyz: np.ndarray,
    segment_COM_frame_imgPoint_XYZ: np.ndarray,
    totalBodyCOM_frame_XYZ: np.ndarray,
    skeleton_segment_lengths_dict: dict,
    processing_parameters: ProcessingParameterModel,
    queue: multiprocessing.Queue,
):
    if queue:
        handler = DirectQueueHandler(queue)
        handler.setFormatter(logging.Formatter(fmt=log_view_logging_format_string, datefmt="%Y-%m-%dT%H:%M:%S"))
        logger.addHandler(handler)

    path_to_folder_where_we_will_save_this_data = processing_parameters.recording_info_model.output_data_folder_path

    logger.info("Saving post-processed data")
    save_numpy_array_to_disk(
        array_to_save=skel3d_frame_marker_xyz,
        file_name="mediaPipeSkel_3d_body_hands_face.npy",
        save_directory=path_to_folder_where_we_will_save_this_data,
    )

    if segment_COM_frame_imgPoint_XYZ is not None:
        logger.info("Saving segment center of mass data")
        save_numpy_array_to_disk(
            array_to_save=segment_COM_frame_imgPoint_XYZ,
            file_name=SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME,
            save_directory=Path(path_to_folder_where_we_will_save_this_data) / CENTER_OF_MASS_FOLDER_NAME,
        )
    else:
        logger.debug("segment_COM_frame_imgPoint_XYZ is None, could not save")

    if totalBodyCOM_frame_XYZ is not None:
        logger.info("Saving total body center of mass data")
        save_numpy_array_to_disk(
            array_to_save=totalBodyCOM_frame_XYZ,
            file_name=TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME,
            save_directory=Path(path_to_folder_where_we_will_save_this_data) / CENTER_OF_MASS_FOLDER_NAME,
        )
    else:
        logger.debug("totalBodyCOM_frame_XYZ is None, could not save")

    if skeleton_segment_lengths_dict is not None:
        logger.info("Saving skeleton segment lengths data")
        save_dictionary_to_json(
            save_path=processing_parameters.recording_info_model.output_data_folder_path,
            file_name="mediapipe_skeleton_segment_lengths.json",
            dictionary=skeleton_segment_lengths_dict,
        )
    else:
        logger.debug("skeleton_segment_lengths_dict is None, could not save")

    if processing_parameters.tracking_model_info.names_and_connections_dict is not None:
        save_dictionary_to_json(
            save_path=processing_parameters.recording_info_model.output_data_folder_path,
            file_name="mediapipe_names_and_connections_dict.json",
            dictionary=processing_parameters.tracking_model_info.names_and_connections_dict,
        )
    else:
        logger.debug("mediapipe_names_and_connections_dict is None, could not save")
