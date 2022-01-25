import logging
from tracemalloc import start
from typing import List
import threading
import queue
import concurrent.futures
import time

from pydantic import BaseModel
import cv2
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

from opencv_camera import OpenCVCamera

from rich import print, inspect
from rich.live import Live
from rich.table import Table


logger = logging.getLogger(__name__)
logger.level = logging.INFO

MAX_NUMBER_OF_CAMERAS = 20

def stuff_incoming_frames_into_a_queue(camera: OpenCVCamera, thread_queue: queue.Queue):
    print('stuff_incoming_frames_into_a_queue starting for {}'.format(camera.name))

    while thread_exit_event.is_set() is False:
        success, image, timestamp_ns = camera.get_next_frame()
        logger.info('{} grabed a frame at timestamp {}'.format(camera.name, timestamp_ns/1e9))
        if not success:
            logger.error('{} failed to grab a frame at timestamp {}'.format(camera.name, timestamp_ns/1e9))
        thread_queue.put((success, camera.name, image, timestamp_ns))




def start_camera_thread(camera: OpenCVCamera, incoming_frames_queue: queue.Queue):
    print('run_camera_in_thread starting for {}'.format(camera.name))
    camera_thread = threading.Thread(
                                target=stuff_incoming_frames_into_a_queue,
                                args=(camera, incoming_frames_queue),
                                name=camera.name+'-thread')
    camera_thread.start()
    return camera_thread




if __name__ == '__main__':

    camera_found_bool = True
    camera_list = []
    this_port_number = -1
    while camera_found_bool:
        this_port_number+=1
        camera =  OpenCVCamera(port_number=this_port_number)
        camera_found_bool = camera.connect()
        if camera_found_bool:
            camera_list.append(camera)

    global thread_exit_event
    thread_exit_event = threading.Event()
    loop_count = 0
    camera_thread_list = [None]*len(camera_list)
    incoming_frames_queue = queue.Queue()

    #%% Start the camera threads (THIS IS WHERE THE MAGIC HAPPENS)
    for this_camera in camera_list:
        camera_thread_list[this_camera.port_number] = start_camera_thread(this_camera, incoming_frames_queue)

    #%% timestamp diagnosis etc

    dict_of_timestamp_lists = {}
    dict_of_fps_mean_lists = {}
    dict_of_fps_std_lists = {}
    for this_camera in camera_list:
        dict_of_timestamp_lists[this_camera.name] = []
        dict_of_fps_mean_lists[this_camera.name] = []
        dict_of_fps_std_lists[this_camera.name] = []

    start_time = time.time()
    end_after_seconds = 5
    while thread_exit_event.is_set() is False:
        time_elapsed = time.time() - start_time
        print('Time remaining: {:.2f}'.format(end_after_seconds - time_elapsed))
        if time_elapsed > end_after_seconds:
            thread_exit_event.set()

        if not incoming_frames_queue.empty():
            this_frame_tuple = incoming_frames_queue.get()
            this_success_bool, this_camera_name, this_image, this_timestamp_ns = this_frame_tuple

            this_timestamp_sec = this_timestamp_ns/1e9

            dict_of_timestamp_lists[this_camera_name].append(this_timestamp_sec)

    list_lengths = [len(this_thing) for this_thing in dict_of_timestamp_lists ]
    for this_camera in camera_list:
        this_cam_timestamps = np.array(dict_of_timestamp_lists[this_camera.name])

    shortest_list_length = np.min([len(dict_of_timestamp_lists[this_key]) for this_key in dict_of_timestamp_lists ])
    out_timestamp_dict = {}

    for this_cam_num, this_camera in enumerate(camera_list):
        out_timestamp_dict[this_camera.name] = np.array(dict_of_timestamp_lists[this_camera.name][:shortest_list_length])
    out_dataframe = pd.DataFrame(out_timestamp_dict)
    out_dataframe.to_csv('~/timestamps.csv')
    
    #%% Plot up them bad bois
    # where 'bad boi'  is defined as a timestamp from each camera
    plt.ion()
    figure = plt.figure(3214, figsize=(15,5))
    ax_timestamps = figure.add_subplot(131)    
    ax_timestamps.set_xlabel('frame number')
    ax_timestamps.set_ylabel('timestamp (unix epoch, sec)')
    ax_timestamps.legend()
    
    ax_framerate = figure.add_subplot(132)
    ax_framerate.set_xlabel('frame number')
    ax_framerate.set_ylabel('framerate (1/np.diff(timestamp, frames/sec)')
    ax_framerate.set_ylim(0, 50)
    ax_framerate.hlines(30, 0, shortest_list_length, linestyles='dashed')    
    
    ax_histogram = figure.add_subplot(133)
    ax_histogram.set_xlabel('bins (fps)')
    ax_histogram.set_ylabel('histogram count(out of {} frames'.format(shortest_list_length))    
    ax_histogram.vlines(30, 0, shortest_list_length, linestyles='dashed')    
    
    
    for this_camera in camera_list:
        this_cam_timestamps = out_timestamp_dict[this_camera.name]
        this_cam_framerate = 1/np.diff(out_timestamp_dict[this_camera.name])
        ax_timestamps.plot(this_cam_timestamps, linewidth=1, marker='.',markersize=1, label=this_camera.name)
        ax_framerate.plot(this_cam_framerate,linewidth=1, marker='.', markersize=1, label=this_camera.name)
        ax_histogram.hist(this_cam_framerate, bins=np.arange(0,50,1), label=this_camera.name)
    plt.show()
    plt.pause(0.1)
    f=9
