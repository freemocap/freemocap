import logging
from typing import List
import threading
import queue
import concurrent.futures

from pydantic import BaseModel
import cv2
import numpy as np
import matplotlib.pyplot as plt

from opencv_camera import OpenCVCamera
from freemocap.prod.cam.cam_detection import DetectPossibleCameras

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



    
def create_figure(number_of_cameras: int, camera_names: List[str]):
    plt.ion()
    fig = plt.figure()
    data_ax = fig.add_subplot(1,number_of_cameras+1,1)
    data_ax.set_title('Camera Timestamps')
    data_ax.set_xlabel('Frame #')
    data_ax.set_ylabel('Timestamp (ns)')

    return fig    

# def update_figure(fig, incoming_frame_tuple):
#     data_ax.cla()
#     data_ax.


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
    
    for this_camera in camera_list:
        camera_thread_list[this_camera.port_number] = start_camera_thread(this_camera, incoming_frames_queue)
        # camera_thread_list[this_camera.port_number].join()
        
    dict_of_timestamp_lists = {}
    for this_camera in camera_list:
        dict_of_timestamp_lists[this_camera.name] = []
        
    while thread_exit_event.is_set() is False:
        if not incoming_frames_queue.empty():
            this_frame_tuple = incoming_frames_queue.get()
            this_success_bool, this_camera_name, this_image, this_timestamp_ns = this_frame_tuple
            dict_of_timestamp_lists[this_camera_name].append(this_timestamp_ns)
        
        
            

        
        

    # with concurrent.futures.ThreadPoolExecutor(max_workers=len(camera_list)) as executor:
    #     for this_camera_number, camera in enumerate(camera_list):
    #         camera_future_list[this_camera_number] = executor.submit(show_camera_stream, camera)
    #     while thread_exit_event.is_set() is False:
    #         loop_count+=1
    #         print('loop_count = {}'.format(loop_count))
    #         for this_camera_number, camera in enumerate(camera_list):
    #             camera_future_list[this_camera_number].result()
  
  
    # for this_camera_number, this_camera in enumerate(camera_list):
    #     print('starting thread for {}'.format(this_camera.name))
    #     camera_thread_list[this_camera_number] = threading.Thread(target=show_camera_stream(this_camera), name=this_camera.name)
    #     camera_thread_list[this_camera_number].start()

