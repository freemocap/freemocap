
from freemocap.core_processes.post_process_skeleton_data.freemocap_utils.postprocessing_widgets.postprocessing_functions.interpolate_data import interpolate_skeleton_data
from freemocap.core_processes.post_process_skeleton_data.freemocap_utils.postprocessing_widgets.postprocessing_functions.filter_data import filter_skeleton_data
from freemocap.core_processes.post_process_skeleton_data.freemocap_utils.postprocessing_widgets.postprocessing_functions.good_frame_finder import find_good_frame
from freemocap.core_processes.post_process_skeleton_data.freemocap_utils.postprocessing_widgets.postprocessing_functions.rotate_skeleton import align_skeleton_with_origin

from freemocap.core_processes.post_process_skeleton_data.freemocap_utils.postprocessing_widgets.visualization_widgets.mediapipe_skeleton_builder import mediapipe_indices

import numpy as np

import threading

from freemocap.core_processes.post_process_skeleton_data.freemocap_utils.constants import (
    TASK_INTERPOLATION,
    TASK_FILTERING,
    TASK_FINDING_GOOD_FRAME,
    TASK_SKELETON_ROTATION,
    PARAM_METHOD,
    PARAM_ORDER,
    PARAM_CUTOFF_FREQUENCY,
    PARAM_SAMPLING_RATE,
    PARAM_ROTATE_DATA,
    PARAM_AUTO_FIND_GOOD_FRAME,
    PARAM_GOOD_FRAME
)

class TaskWorkerThread(threading.Thread):
    def __init__(self, raw_skeleton_data:np.ndarray, task_list:list, settings:dict, task_running_callback=None, task_completed_callback=None, all_tasks_finished_callback=None):
        super().__init__()

        self.raw_skeleton_data = raw_skeleton_data

        self.available_tasks = {
            #dictionary of all tasks that could be called in this thread, and their associated functions
            TASK_INTERPOLATION: self.interpolate_task,
            TASK_FILTERING: self.filter_task,
            TASK_FINDING_GOOD_FRAME: self.find_good_frame_task,
            TASK_SKELETON_ROTATION: self.rotate_skeleton_task,
        }

        #create a dictionary based of the tasks that were passed to the thread, and an empty results tab for each
        self.tasks = {task_name: {'function': self.available_tasks[task_name], 'result': None} for task_name in task_list}

        self.settings = settings

        self.task_running_callback = task_running_callback
        self.task_completed_callback = task_completed_callback
        self.all_tasks_finished_callback = all_tasks_finished_callback



    def run(self):
        for task_info in self.tasks.values(): #clear any previous results 
            task_info['result'] = None

        for task_name, task_info in self.tasks.items():

            if self.task_running_callback is not None:
                self.task_running_callback(task_name)
            
            #run the function for each task and return a bool of if it is completed, and a result object
            is_completed, result = task_info['function']() 
            
            task_info['result'] = result

            #depending on if callback functions have been passed, return the result of the function, or None
            #if the task was not completed
            if is_completed:
                if self.task_completed_callback is not None:
                    self.task_completed_callback(task_name, result)
            else:
                if self.task_completed_callback is not None:
                    self.task_completed_callback(task_name, None)

        if self.all_tasks_finished_callback is not None:
            self.all_tasks_finished_callback(self.tasks)

    def interpolate_task(self):
        interpolation_values_dict = self.settings[TASK_INTERPOLATION]
        interpolated_skeleton = interpolate_skeleton_data(self.raw_skeleton_data, method_to_use=interpolation_values_dict[PARAM_METHOD], order=interpolation_values_dict[PARAM_ORDER])
        return True,interpolated_skeleton

    def filter_task(self):
        filter_values_dict = self.settings[TASK_FILTERING]
        filtered_skeleton = filter_skeleton_data(self.tasks[TASK_INTERPOLATION]['result'], order=filter_values_dict[PARAM_ORDER], cutoff=filter_values_dict[PARAM_CUTOFF_FREQUENCY], sampling_rate=filter_values_dict[PARAM_SAMPLING_RATE])
        return True,filtered_skeleton

    def find_good_frame_task(self):
        good_frame_values_dict = self.settings[TASK_SKELETON_ROTATION]
        
        if good_frame_values_dict[PARAM_ROTATE_DATA]:
            #if auto find is selected, find the good frame - if it is not, use the user entered value
            if good_frame_values_dict[PARAM_AUTO_FIND_GOOD_FRAME]:
                self.good_frame = find_good_frame(self.tasks[TASK_FILTERING]['result'], skeleton_indices=mediapipe_indices, initial_velocity_guess=.5)
            else:
                self.good_frame = int(good_frame_values_dict[PARAM_GOOD_FRAME])
            return True, self.good_frame
        else:
            #if no rotation is needed, we don't need to run the good frame finder
            self.good_frame = 0
            return False, self.good_frame

    def rotate_skeleton_task(self):
        rotate_values_dict = self.settings[TASK_SKELETON_ROTATION]
        if rotate_values_dict[PARAM_ROTATE_DATA]:
            origin_aligned_skeleton = align_skeleton_with_origin(self.tasks[TASK_FILTERING]['result'], mediapipe_indices, self.good_frame)[0]
            return True, origin_aligned_skeleton
        else:
            origin_aligned_skeleton = None
            return False, origin_aligned_skeleton

