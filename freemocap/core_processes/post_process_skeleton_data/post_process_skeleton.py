import logging
import multiprocessing
from pathlib import Path
from typing import Union

import numpy as np
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
from skellytracker.trackers.base_tracker.model_info import ModelInfo


from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel
from freemocap.system.logging.configure_logging import log_view_logging_format_string
from freemocap.system.logging.queue_logger import DirectQueueHandler
from freemocap.system.paths_and_filenames.file_and_folder_names import LOG_VIEW_PROGRESS_BAR_STRING

from freemocap.system.logging.configure_logging import log_view_logging_format_string
from freemocap.system.logging.queue_logger import DirectQueueHandler
from freemocap.system.paths_and_filenames.file_and_folder_names import LOG_VIEW_PROGRESS_BAR_STRING

logger = logging.getLogger(__name__)


class PostProcessedDataHandler:
    def __init__(self):
        self.processed_skeleton = None

    def data_callback(self, processed_skeleton: np.ndarray):
        self.processed_skeleton = processed_skeleton

def save_numpy_array_to_disk(
        array_to_save: np.ndarray,
        file_name: str,
        save_directory: Union[str, Path]
):
    if not file_name.endswith(".npy"):
        file_name += ".npy"
    Path(save_directory).mkdir(parents=True, exist_ok=True)
    np.save(
        str(Path(save_directory) / file_name),
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


def run_post_processing_worker(
    raw_skel3d_frame_marker_xyz: np.ndarray, settings_dictionary: dict, landmark_names: list
) -> np.ndarray:
    def handle_thread_finished(results, post_processed_data_handler: PostProcessedDataHandler):
        processed_skeleton = results[TASK_FILTERING]["result"]
        post_processed_data_handler.data_callback(processed_skeleton=processed_skeleton)

    task_list = [TASK_INTERPOLATION, TASK_FILTERING, TASK_FINDING_GOOD_FRAME, TASK_SKELETON_ROTATION]

    post_processed_data_handler = PostProcessedDataHandler()

    logger.info("Starting post-processing worker thread")
    logger.info(LOG_VIEW_PROGRESS_BAR_STRING)

    worker_thread = TaskWorkerThread(
        raw_skeleton_data=raw_skel3d_frame_marker_xyz,
        task_list=task_list,
        settings=settings_dictionary,
        landmark_names=landmark_names,
        all_tasks_finished_callback=lambda results: handle_thread_finished(results, post_processed_data_handler),
    )
    worker_thread.start()
    worker_thread.join()
    logger.info("Done with gap filling, filtering, and aligning")

    return post_processed_data_handler.processed_skeleton


def post_process_data(
    recording_processing_parameter_model, raw_skel3d_frame_marker_xyz: np.ndarray, queue: multiprocessing.Queue
) -> np.ndarray:
    if queue:
        handler = DirectQueueHandler(queue)
        handler.setFormatter(logging.Formatter(fmt=log_view_logging_format_string, datefmt="%Y-%m-%dT%H:%M:%S"))
        logger.addHandler(handler)
    filter_sampling_rate, filter_cutoff_frequency, filter_order = get_settings_from_parameter_tree(
        recording_processing_parameter_model
    )
    adjusted_settings = adjust_default_settings(filter_sampling_rate, filter_cutoff_frequency, filter_order)
    processed_skeleton_array = run_post_processing_worker(
        raw_skel3d_frame_marker_xyz=raw_skel3d_frame_marker_xyz,
        settings_dictionary=adjusted_settings,
        landmark_names = get_landmark_names(model_info=recording_processing_parameter_model.tracking_model_info),
    )

    return processed_skeleton_array

def get_landmark_names(model_info: ModelInfo) -> list:
    if hasattr(model_info, "body_landmark_names"):
        return model_info.body_landmark_names
    elif hasattr(model_info, "landmark_names"):
        return model_info.landmark_names
    else:
        raise AttributeError("Model does not have landmark names")
