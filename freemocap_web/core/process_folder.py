import logging
import multiprocessing
from pathlib import Path

import numpy as np
import pandas as pd

from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.get_anipose_calibration_object import (
    load_anipose_calibration_toml_from_path,
)
from freemocap.core_processes.capture_volume_calibration.triangulate_3d_data import (
    triangulate_3d_data,
)
from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.convert_mediapipe_npy_to_csv import (
    convert_mediapipe_npy_to_csv,
)
from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.data_models.mediapipe_skeleton_names_and_connections import (
    mediapipe_names_and_connections_dict,
)
from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.mediapipe_skeleton_detector import (
    MediaPipeSkeletonDetector,
)
from freemocap.core_processes.post_process_skeleton_data.calculate_center_of_mass import run_center_of_mass_calculations
from freemocap.core_processes.post_process_skeleton_data.estimate_skeleton_segment_lengths import (
    estimate_skeleton_segment_lengths,
    mediapipe_skeleton_segment_definitions,
)
from freemocap.core_processes.post_process_skeleton_data.post_process_skeleton import (
    post_process_data,
    save_skeleton_array_to_npy,
)
from freemocap.core_processes.post_process_skeleton_data.process_single_camera_skeleton_data import (
    process_single_camera_skeleton_data,
)
from freemocap.data_layer.data_saver.data_saver import DataSaver
from freemocap.data_layer.recording_models.post_processing_parameter_models import PostProcessingParameterModel
from freemocap.system.logging.configure_logging import log_view_logging_format_string
from freemocap.system.logging.queue_logger import DirectQueueHandler
from freemocap.system.paths_and_filenames.file_and_folder_names import (
    RAW_DATA_FOLDER_NAME,
    SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME,
    CENTER_OF_MASS_FOLDER_NAME,
    TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME,
    MEDIAPIPE_BODY_3D_DATAFRAME_CSV_FILE_NAME,
)
from freemocap.tests.test_image_tracking_data_shape import (
    test_image_tracking_data_shape,
)
from freemocap.tests.test_mediapipe_skeleton_data_shape import test_mediapipe_skeleton_data_shape
from freemocap.utilities.geometry.rotate_by_90_degrees_around_x_axis import rotate_by_90_degrees_around_x_axis
from freemocap.utilities.save_dictionary_to_json import save_dictionary_to_json

logger = logging.getLogger(__name__)


def process_recording_folder(
    recording_processing_parameter_model: PostProcessingParameterModel,
    kill_event: multiprocessing.Event = None,
):
    path_to_folder_where_we_will_save_this_data = rec.recording_info_model.output_data_folder_path

    logger.info("Estimating skeleton segment lengths...")

    save_dictionary_to_json(
        save_path=rec.recording_info_model.output_data_folder_path,
        file_name="mediapipe_skeleton_segment_lengths.json",
        dictionary=skeleton_segment_lengths_dict,
    )

    save_dictionary_to_json(
        save_path=rec.recording_info_model.output_data_folder_path,
        file_name="mediapipe_names_and_connections_dict.json",
        dictionary=mediapipe_names_and_connections_dict,
    )

    # TODO - move this data output method *above* the sloppy stuff above and deprecate the sloppy stuff (gracefully enough not to bork hypothetical users' workflows)
    DataSaver(recording_folder_path=rec.recording_info_model.path).save_all()

    logger.info(f"Done processing {rec.recording_info_model.path}")
