
import numpy as np
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


def handle_post_process_results(task_results: dict, data_handler: PostProcessedDataHandler):
    filtered_skeleton_data = task_results[TASK_FILTERING]['result']
    origin_aligned_skeleton_data = task_results[TASK_SKELETON_ROTATION]['result']

    data_handler.set_filtered_data(filtered_skeleton_data=filtered_skeleton_data)
    data_handler.set_origin_aligned_data(origin_aligned_skeleton_data=origin_aligned_skeleton_data)


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
    task_list = [TASK_INTERPOLATION, TASK_FILTERING, TASK_FINDING_GOOD_FRAME, TASK_SKELETON_ROTATION]
    post_processed_data_handler = PostProcessedDataHandler()
    worker_thread = TaskWorkerThread(raw_skeleton_data=raw_skel3d_frame_marker_xyz, task_list=task_list,
                                     settings=settings_dictionary,
                                     all_tasks_finished_callback=handle_post_process_results)
    worker_thread.start()

    return post_processed_data_handler


def save_post_processed_data(processed_skel3d_frame_marker_xyz: np.ndarray,
                             path_to_folder_where_we_will_save_this_data):
    Path(path_to_folder_where_we_will_save_this_data).mkdir(parents=True, exist_ok=True)
    np.save(
        str(path_to_folder_where_we_will_save_this_data / "mediaPipeSkel_3d_body_hands_face.npy"),
        processed_skel3d_frame_marker_xyz,
    )


def post_process_data(recording_processing_parameter_model, raw_skel3d_frame_marker_xyz: np.ndarray,
                      path_to_folder_where_we_will_save_this_data):
    filter_sampling_rate, filter_cutoff_frequency, filter_order = get_settings_from_parameter_tree(
        recording_processing_parameter_model)
    adjusted_settings = adjust_default_settings(filter_sampling_rate, filter_cutoff_frequency, filter_order)
    post_processed_data_handler = run_post_processing_worker(raw_skel3d_frame_marker_xyz=raw_skel3d_frame_marker_xyz,
                                                             settings_dictionary=adjusted_settings)
    processed_skeleton_data = post_processed_data_handler.origin_aligned_skeleton_data
    save_post_processed_data(processed_skel3d_frame_marker_xyz=processed_skeleton_data,
                             path_to_folder_where_we_will_save_this_data=path_to_folder_where_we_will_save_this_data)
#
