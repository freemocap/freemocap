from typing import Union

import numpy as np
from pathlib import Path
import logging

from skellyforge.freemocap_utils.config import default_settings
from skellyforge.freemocap_utils.constants import (
    TASK_FILTERING,
    PARAM_CUTOFF_FREQUENCY,
    PARAM_SAMPLING_RATE,
    PARAM_ORDER,
    PARAM_ROTATE_DATA,
    TASK_SKELETON_ROTATION,
    TASK_INTERPOLATION,
    TASK_FINDING_GOOD_FRAME,
)
from skellyforge.freemocap_utils.postprocessing_widgets.task_worker_thread import TaskWorkerThread

logger = logging.getLogger(__name__)


class PostProcessedDataHandler:
    def __init__(self):
        self.processed_skeleton = None

    def data_callback(self, processed_skeleton: np.ndarray):
        self.processed_skeleton = processed_skeleton


def save_skeleton_array_to_npy(
    array_to_save: np.ndarray, skeleton_file_name: str, path_to_folder_where_we_will_save_this_data: Union[str, Path]
):
    if not skeleton_file_name.endswith(".npy"):
        skeleton_file_name += ".npy"
    Path(path_to_folder_where_we_will_save_this_data).mkdir(parents=True, exist_ok=True)
    np.save(
        str(Path(path_to_folder_where_we_will_save_this_data) / skeleton_file_name),
        array_to_save,
    )


def get_settings_from_parameter_tree(recording_processing_parameter_model):
    rec = recording_processing_parameter_model

    filter_sampling_rate = rec.post_processing_parameters_model.framerate
    filter_cutoff_frequency = rec.post_processing_parameters_model.butterworth_filter_parameters.cutoff_frequency
    filter_order = rec.post_processing_parameters_model.butterworth_filter_parameters.order

    return filter_sampling_rate, filter_cutoff_frequency, filter_order


def adjust_default_settings(filter_sampling_rate, filter_cutoff_frequency, filter_order):
    adjusted_settings = default_settings.copy()

    adjusted_settings[TASK_FILTERING][PARAM_CUTOFF_FREQUENCY] = filter_cutoff_frequency
    adjusted_settings[TASK_FILTERING][PARAM_SAMPLING_RATE] = filter_sampling_rate
    adjusted_settings[TASK_FILTERING][PARAM_ORDER] = filter_order
    adjusted_settings[TASK_SKELETON_ROTATION][PARAM_ROTATE_DATA] = False

    return adjusted_settings


def run_post_processing_worker(raw_skel3d_frame_marker_xyz: np.ndarray, settings_dictionary: dict):
    def handle_thread_finished(results, post_processed_data_handler: PostProcessedDataHandler):
        processed_skeleton = results[TASK_FILTERING]["result"]
        post_processed_data_handler.data_callback(processed_skeleton=processed_skeleton)

    task_list = [TASK_INTERPOLATION, TASK_FILTERING, TASK_FINDING_GOOD_FRAME, TASK_SKELETON_ROTATION]

    post_processed_data_handler = PostProcessedDataHandler()

    logger.info("Starting post-processing worker thread")

    worker_thread = TaskWorkerThread(
        raw_skeleton_data=raw_skel3d_frame_marker_xyz,
        task_list=task_list,
        settings=settings_dictionary,
        all_tasks_finished_callback=lambda results: handle_thread_finished(results, post_processed_data_handler),
    )
    worker_thread.start()
    worker_thread.join()
    logger.info("Done with gap filling, filtering, and aligning")

    return post_processed_data_handler.processed_skeleton


def post_process_data(recording_processing_parameter_model, raw_skel3d_frame_marker_xyz: np.ndarray):
    filter_sampling_rate, filter_cutoff_frequency, filter_order = get_settings_from_parameter_tree(
        recording_processing_parameter_model
    )
    adjusted_settings = adjust_default_settings(filter_sampling_rate, filter_cutoff_frequency, filter_order)
    processed_skeleton_array = run_post_processing_worker(
        raw_skel3d_frame_marker_xyz=raw_skel3d_frame_marker_xyz, settings_dictionary=adjusted_settings
    )

    return processed_skeleton_array
