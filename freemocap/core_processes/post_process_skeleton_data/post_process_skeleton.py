
import numpy as np
from pathlib import Path

from freemocap.core_processes.post_process_skeleton_data.freemocap_utils.postprocessing_widgets.task_worker_thread \
    import TaskWorkerThread
from freemocap.core_processes.post_process_skeleton_data.freemocap_utils.config import default_settings
from freemocap.core_processes.post_process_skeleton_data.freemocap_utils.constants import (
    TASK_INTERPOLATION,
    TASK_FILTERING,
    TASK_FINDING_GOOD_FRAME,
    TASK_SKELETON_ROTATION,
    PARAM_CUTOFF_FREQUENCY,
    PARAM_SAMPLING_RATE,
    PARAM_ORDER
)


class PostProcessedDataHandler:
    def __init__(self):
        self.origin_aligned_skeleton_data = None
        self.filtered_skeleton_data = None

    def set_filtered_data(self, filtered_skeleton_data: np.ndarray):


        self.filtered_skeleton_data = filtered_skeleton_data

    def set_origin_aligned_data(self, origin_aligned_skeleton_data: np.ndarray):
        self.origin_aligned_skeleton_data = origin_aligned_skeleton_data


def handle_post_process_results(task_results: dict, save_path: str):
    filtered_skeleton_data = task_results[TASK_FILTERING]['result']
    origin_aligned_skeleton_data = task_results[TASK_SKELETON_ROTATION]['result']

    # set the data
    # data_handler.set_filtered_data(filtered_skeleton_data=filtered_skeleton_data)
    # data_handler.set_origin_aligned_data(origin_aligned_skeleton_data=origin_aligned_skeleton_data)

    # save the data
    save_post_processed_data(processed_skel3d_frame_marker_xyz=origin_aligned_skeleton_data,
                             path_to_folder_where_we_will_save_this_data=save_path)


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

    return adjusted_settings


def run_post_processing_worker(raw_skel3d_frame_marker_xyz: np.ndarray, settings_dictionary: dict, save_path: str, on_done_function):

    def handle_thread_finished(results,save_path):
        handle_post_process_results(results, save_path)
        on_done_function(results[TASK_SKELETON_ROTATION]['result'])


    task_list = [TASK_INTERPOLATION, TASK_FILTERING, TASK_FINDING_GOOD_FRAME, TASK_SKELETON_ROTATION]
    post_processed_data_handler = PostProcessedDataHandler()
    worker_thread = TaskWorkerThread(
        raw_skeleton_data=raw_skel3d_frame_marker_xyz,
        task_list=task_list,
        settings=settings_dictionary,
        all_tasks_finished_callback=lambda results: handle_thread_finished(results, save_path)
    )
    worker_thread.start()
    worker_thread.join()

    return post_processed_data_handler

def save_post_processed_data(processed_skel3d_frame_marker_xyz: np.ndarray,
                             path_to_folder_where_we_will_save_this_data):
    Path(path_to_folder_where_we_will_save_this_data).mkdir(parents=True, exist_ok=True)
    np.save(
        str(Path(path_to_folder_where_we_will_save_this_data) / "mediaPipeSkel_3d_body_hands_face.npy"),
        processed_skel3d_frame_marker_xyz,
    )


def post_process_data(recording_processing_parameter_model, raw_skel3d_frame_marker_xyz: np.ndarray,
                      path_to_folder_where_we_will_save_this_data, on_done_function=None):
    filter_sampling_rate, filter_cutoff_frequency, filter_order = get_settings_from_parameter_tree(
        recording_processing_parameter_model)
    adjusted_settings = adjust_default_settings(filter_sampling_rate, filter_cutoff_frequency, filter_order)
    post_processed_data_handler = run_post_processing_worker(
        raw_skel3d_frame_marker_xyz=raw_skel3d_frame_marker_xyz,
        settings_dictionary=adjusted_settings,
        save_path=path_to_folder_where_we_will_save_this_data,
        on_done_function = on_done_function
    )
    return post_processed_data_handler.origin_aligned_skeleton_data
