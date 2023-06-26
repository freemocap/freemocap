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
        self.processed_skeleton = None

    def data_callback(self, processed_skeleton):
        self.processed_skeleton = processed_skeleton


def save_array_to_file(array_to_save: np.ndarray, skeleton_file_name: str, path_to_folder_where_we_will_save_this_data: str):
    Path(path_to_folder_where_we_will_save_this_data).mkdir(parents=True, exist_ok=True)
    np.save(
        str(Path(path_to_folder_where_we_will_save_this_data) / skeleton_file_name),
        array_to_save,
    )


# def handle_post_process_results(task_results: dict, save_path: str):
#     filtered_skeleton_data = task_results[TASK_FILTERING]['result']
#     origin_aligned_skeleton_data = task_results[TASK_SKELETON_ROTATION]['result']
#
#     # save the data
#     save_post_processed_data(processed_skel3d_frame_marker_xyz=origin_aligned_skeleton_data,
#                              path_to_folder_where_we_will_save_this_data=save_path)


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


def run_post_processing_worker(raw_skel3d_frame_marker_xyz: np.ndarray, settings_dictionary: dict):

    def handle_thread_finished(results,post_processed_data_handler:PostProcessedDataHandler):
        processed_skeleton = results[TASK_SKELETON_ROTATION]['result']

        post_processed_data_handler.data_callback(processed_skeleton =processed_skeleton)

    task_list = [TASK_INTERPOLATION, TASK_FILTERING, TASK_FINDING_GOOD_FRAME, TASK_SKELETON_ROTATION]

    post_processed_data_handler = PostProcessedDataHandler()

    worker_thread = TaskWorkerThread(
        raw_skeleton_data=raw_skel3d_frame_marker_xyz,
        task_list=task_list,
        settings=settings_dictionary,
        all_tasks_finished_callback=lambda results: handle_thread_finished(results, post_processed_data_handler)
    )
    worker_thread.start()
    worker_thread.join()

    return post_processed_data_handler.processed_skeleton

# def save_post_processed_data(processed_skel3d_frame_marker_xyz: np.ndarray,
#                              path_to_folder_where_we_will_save_this_data):
#     Path(path_to_folder_where_we_will_save_this_data).mkdir(parents=True, exist_ok=True)
#     np.save(
#         str(Path(path_to_folder_where_we_will_save_this_data) / "mediaPipeSkel_3d_body_hands_face.npy"),
#         processed_skel3d_frame_marker_xyz,
#     )


def post_process_data(recording_processing_parameter_model, raw_skel3d_frame_marker_xyz: np.ndarray):
    filter_sampling_rate, filter_cutoff_frequency, filter_order = get_settings_from_parameter_tree(
        recording_processing_parameter_model)
    adjusted_settings = adjust_default_settings(filter_sampling_rate, filter_cutoff_frequency, filter_order)
    processed_skeleton_array = run_post_processing_worker(
        raw_skel3d_frame_marker_xyz=raw_skel3d_frame_marker_xyz,
        settings_dictionary=adjusted_settings)

    return processed_skeleton_array
