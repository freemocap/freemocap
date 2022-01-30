#%%
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
        thread_queue.put((success, camera.port_number, camera.name, image, timestamp_ns))




def start_camera_thread(camera: OpenCVCamera, incoming_frames_queue: queue.Queue):
    print('run_camera_in_thread starting for {}'.format(camera.name))
    camera_thread = threading.Thread(
                                target=stuff_incoming_frames_into_a_queue,
                                args=(camera, incoming_frames_queue),
                                name=camera.name+'-thread')
    camera_thread.start()
    return camera_thread

def display_image_on_its_cv2_named_window(cam_window_name: str, image: np.ndarray, ):
    cv2.imshow(cam_window_name, image)
    key = cv2.waitKey(1)

    if key == 27: #esc key kills all streams, I think
        thread_exit_event.set()

    if thread_exit_event.is_set():
        cv2.destroyAllWindows()

def create_video_viewing_window(camera_name:str = 'Cam', window_location = (0,0)):
    window_name = camera_name + " - Press ESC to exit"
    cv2.namedWindow(window_name)
    cv2.moveWindow(window_name, window_location[0], window_location[1])
    return window_name


#%% connect to all available cameras

camera_found_bool = True
camera_list = []
this_port_number = -1
while camera_found_bool:
    this_port_number+=1
    camera =  OpenCVCamera(port_number=this_port_number)
    camera_found_bool = camera.connect()
    if camera_found_bool:
        camera_list.append(camera)

number_of_cameras = len(camera_list)

global thread_exit_event
thread_exit_event = threading.Event()
loop_count = 0
camera_thread_list = [None]*len(camera_list)
incoming_frames_queue = queue.Queue()

#%% set some things up before we start streaming
# setting up to grab incoming timestamps etc
dict_of_timestamp_lists = {}
dict_of_fps_mean_lists = {}
dict_of_fps_std_lists = {}
for this_camera in camera_list:
    dict_of_timestamp_lists[this_camera.name] = []
    dict_of_fps_mean_lists[this_camera.name] = []
    dict_of_fps_std_lists[this_camera.name] = []

# #create cv2 named windows where we'll display incoming frames
cam_window_name_dict = {}
display_image_scale_factor = 2
scaled_image_width = int(camera_list[0].resolution_width/display_image_scale_factor)
scaled_image_height = int(camera_list[0].resolution_height/display_image_scale_factor)
window_buffer = 50
for this_camera in camera_list:
    #tile windows across monitor
    window_location_x = this_camera.port_number*scaled_image_width
    window_location_y=0
    if window_location_x+scaled_image_width > 1920:
        window_location_x -= 1920
        window_location_y = scaled_image_height+window_buffer
    elif window_location_x+scaled_image_width > 1920*2:
        window_location_x -= 1920*2
        window_location_y = scaled_image_height*2
    print('Creating window for {} at ({},{})'.format(this_camera.name, str(window_location_x), str(window_location_y)))
    cam_window_name_dict[this_camera.name] = create_video_viewing_window(this_camera.name, (window_location_x, window_location_y))

# multi_cam_widow_name = create_video_viewing_window('MultiCamera')

# #were going to scale down each incoming camera image and tile it, so we only have to display one big thing (which is faster than displaying many small things)
# multi_image_number_of_tiles_per_side = int(np.ceil(np.sqrt(number_of_cameras)))
# num_extra_spots_in_multi_image = multi_image_number_of_tiles_per_side - number_of_cameras
# display_image_scale_factor = 2
# scaled_image_width = int(camera_list[0].resolution_width/display_image_scale_factor)
# scaled_image_height = int(camera_list[0].resolution_height/display_image_scale_factor)

# scaled_image_black_frame = np.zeros((scaled_image_height, scaled_image_width, 3))
# multi_image_holder_list_of_lists = []

# for iter in range(multi_image_number_of_tiles_per_side):
#     blank_row = [scaled_image_black_frame.copy() for each in range(multi_image_number_of_tiles_per_side)]
#     multi_image_holder_list_of_lists.append(blank_row)

# each_cameras_multi_image_address = []
# for this_cam_num in range(number_of_cameras):
#     this_cam_row = int(np.floor(this_cam_num/multi_image_number_of_tiles_per_side))
#     this_cam_col = this_cam_num - this_cam_row*multi_image_number_of_tiles_per_side
#     each_cameras_multi_image_address.append((this_cam_row, this_cam_col))



#%%
###########################################################################################
###########################################################################################
##
##  Start the camera threads (THIS IS WHERE THE MAGIC HAPPENS)
##
###########################################################################################
###########################################################################################

for this_camera in camera_list:
    camera_thread_list[this_camera.port_number] = start_camera_thread(this_camera, incoming_frames_queue)

#
# start the MainThread loop
approx_start_time = time.time()
end_after_seconds = 20 #or on pressing ESC
qsize = []
while not thread_exit_event.is_set():
    time_elapsed = time.time() - approx_start_time
    this_qsize = incoming_frames_queue.qsize()
    qsize.append(this_qsize)
    print('Time remaining: {:3.2f} - Queue size: {:3.0f} '.format(end_after_seconds - time_elapsed, this_qsize))
    if time_elapsed > end_after_seconds:
        thread_exit_event.set()
        cv2.destroyAllWindows()

    if not incoming_frames_queue.empty():
        this_frame_tuple = incoming_frames_queue.get() #<- grab the most recent frame_tuple and do stuff with it
        this_success_bool, this_camera_number, this_camera_name, this_image, this_timestamp_ns = this_frame_tuple
        this_timestamp_sec = this_timestamp_ns/1e9
        dict_of_timestamp_lists[this_camera_name].append(this_timestamp_sec)

    elif qsize[-1] < 10: #only display images if queue isn't over filled
        # this_cam_address = each_cameras_multi_image_address[this_camera_number]
        # print(this_cam_address)
        # resized_image = cv2.resize(this_image, (scaled_image_width, scaled_image_height))
        # multi_image_holder_list_of_lists[this_cam_address[0]][this_cam_address[1]] = resized_image
        
        # each_row_of_multi_im = []
        # for this_row in range(multi_image_number_of_tiles_per_side):
        #     each_row_of_multi_im.append(np.hstack(multi_image_holder_list_of_lists[this_row]))
        # this_multi_im = np.vstack(each_row_of_multi_im)
        # this_multi_im = cv2.normalize(src=this_multi_im, dst=None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        # display_image_on_its_cv2_named_window(multi_cam_widow_name, this_multi_im)
        image_height, image_width, image_channels = this_image.shape
        scale_height = int(image_height/display_image_scale_factor)
        scale_width = int(image_width/display_image_scale_factor)
        display_image_on_its_cv2_named_window(cam_window_name_dict[this_camera_name], cv2.resize(this_image, (scale_width, scale_height)))

#%%

list_lengths = [len(this_thing) for this_thing in dict_of_timestamp_lists ]
for this_camera in camera_list:
    this_cam_timestamps = np.array(dict_of_timestamp_lists[this_camera.name])

number_of_frames = np.min([len(dict_of_timestamp_lists[this_key]) for this_key in dict_of_timestamp_lists ]) #truncate all timestamp lists to match frame count of shortest
out_timestamp_dict = {}

for this_cam_num, this_camera in enumerate(camera_list):
    out_timestamp_dict[this_camera.name] = np.array(dict_of_timestamp_lists[this_camera.name][:number_of_frames])
out_dataframe = pd.DataFrame(out_timestamp_dict)
out_dataframe.to_csv('~/timestamps.csv')

#%% Plot up them bad bois
# where 'bad boi'  is defined as a timestamp from each camera
# plt.ion() #<- allows for fiddling, but need to set breakpoint and call plt.show() to see the plots
figure = plt.figure(3214, figsize=(18,5))
ax_timestamps = figure.add_subplot(141)
ax_timestamps.set_xlabel('frame number')
ax_timestamps.set_ylabel('timestamp (unix epoch, sec)')

ax_frame_duration = figure.add_subplot(142)
ax_frame_duration.set_xlabel('frame number')
ax_frame_duration.set_ylabel('framerate (1/np.diff(timestamp, frames/sec)')
ax_frame_duration.set_ylim(0, .1)

ax_histogram = figure.add_subplot(143)
ax_histogram.set_xlabel('bins (fps)')
ax_histogram.set_ylabel('histogram count(out of {} frames'.format(number_of_frames))

ax_qsize = figure.add_subplot(144)
ax_qsize.set_xlabel('frame/loop count')
ax_qsize.set_ylabel('incoming frames queueue size')
ax_qsize.plot(qsize, '-',linewidth=.5, alpha=.5)
ax_qsize.plot(qsize, 'k.')

for this_camera in camera_list:
    this_cam_timestamps = out_timestamp_dict[this_camera.name]
    this_cam_frame_duration = np.diff(out_timestamp_dict[this_camera.name])
    this_cam_framerate = 1/this_cam_frame_duration

    ax_timestamps.plot(this_cam_timestamps, 'o',markersize=1, alpha=.5, label=this_camera.name)
    ax_frame_duration.plot(this_cam_frame_duration, '-o', markersize=1, alpha=.5, label=this_camera.name)
    ax_histogram.hist(this_cam_framerate, bins=np.arange(0,50,1), alpha=.5,label=this_camera.name)

#reference lines (i.e. 'ideal' numbers)
ideal_framerate = 30
approx_start_time = this_cam_timestamps[0] #just for the last camera, but it's fine for this visualization
ideal_end_time = approx_start_time + number_of_frames/ideal_framerate
ideal_timestamps = np.linspace(approx_start_time, ideal_end_time, number_of_frames)

ideal_line_label = 'ideal for {}fps'.format(ideal_framerate)
ax_frame_duration.plot([ 0, number_of_frames], [1/ideal_framerate, 1/ideal_framerate],'--', label=ideal_line_label, color='black')
ax_histogram.vlines(ideal_framerate, 0, number_of_frames, linestyles='dashed', label=ideal_line_label)
ax_timestamps.plot(ideal_timestamps, '--', color='black', label=ideal_line_label)
ax_frame_duration.legend()

plt.show()
plt.pause(0.1)#put a breakpoint here to view/interact with figure if `plt.ion()` is active

