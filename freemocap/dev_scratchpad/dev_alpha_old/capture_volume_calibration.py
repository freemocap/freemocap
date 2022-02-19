from rich import print
from rich.console import Console
from FMC_MultiCamera import FMC_MultiCamera
import socket
from pathlib import Path
from pathos.helpers import mp as pathos_mp_helper
import cv2
from copy import deepcopy
import numpy as np

from itertools import combinations

import matplotlib.pyplot as plt

aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_250)
charuco_length = 7
charuco_width = 5

board = cv2.aruco.CharucoBoard_create(charuco_length, charuco_width, 1, .8, aruco_dict)
num_charuco_corners = (charuco_length - 1) * (charuco_width - 1)


def detect_charuco_board(image):
    """
    Charuco base pose estimation.
    more-or-less copied from - https://mecaruco2.readthedocs.io/en/latest/notebooks_rst/Aruco/sandbox/ludovic/aruco_calibration_rotation.html
    """
    charuco_corners = []
    charuco_ids = []

    # SUB PIXEL CORNER DETECTION CRITERION
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.00001)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    aruco_square_corners, aruco_square_ids, rejectedImgPoints = cv2.aruco.detectMarkers(gray, aruco_dict)

    if len(aruco_square_corners) > 0:
        # SUB PIXEL DETECTION
        for this_corner in aruco_square_corners:
            cv2.cornerSubPix(gray, this_corner,
                             winSize=(3, 3),
                             zeroZone=(-1, -1),
                             criteria=criteria)
        res2 = cv2.aruco.interpolateCornersCharuco(aruco_square_corners, aruco_square_ids, gray, board)

        if res2[1] is not None and res2[2] is not None and len(res2[1]) > 3:
            charuco_corners = res2[1]
            charuco_ids = res2[2]

    return charuco_corners, charuco_ids, aruco_square_corners, aruco_square_ids


if __name__ == "__main__":
    pathos_mp_helper.freeze_support()

    console = Console()  # create rich console to catch and print exceptions

    this_computer_name = socket.gethostname()

    freemocap_data_path = None
    in_rotation_codes_list = None
    in_cams_to_use_list = None

    if this_computer_name == 'jon-hallway-XPS-8930':
        freemocap_data_path = Path('/home/jon/Dropbox/FreeMoCapProject/FreeMocap_Data')
        in_rotation_codes_list = ['cv2.ROTATE_90_COUNTERCLOCKWISE', 'cv2.ROTATE_90_COUNTERCLOCKWISE',
                                  'cv2.ROTATE_90_CLOCKWISE', 'cv2.ROTATE_90_CLOCKWISE', 'cv2.ROTATE_90_CLOCKWISE', ]
    elif this_computer_name == 'DESKTOP-DCG6K4F':
        freemocap_data_path = Path(r'C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data')
    elif this_computer_name == 'DESKTOP-V3D343U':
        freemocap_data_path = Path(r'C:\Users\WindowsPC_Hallway\Dropbox\FreeMoCapProject\FreeMocap_Data')
        in_cams_to_use_list = [0, 1, 2, 3]
    elif this_computer_name == 'Jons-MacBook-Pro.local':
        freemocap_data_path = Path('/Users/jon/Dropbox/FreeMoCapProject')

    try:
        multi_cam = FMC_MultiCamera(cams_to_use_list=in_cams_to_use_list, show_multi_cam_stream_bool=False,
                                    freemocap_data_folder=str(freemocap_data_path),
                                    rotation_codes_list=in_rotation_codes_list)
        multi_cam.start()

        console.rule('Launching Multi Cam Viewer')
        current_loop_count = 0
        aruco_square_corners = [[] for _ in range(multi_cam.num_cams)]
        aruco_square_ids = [np.array([]) for _ in range(multi_cam.num_cams)]
        charuco_corners = [np.array([]) for _ in range(multi_cam.num_cams)]
        charuco_ids = [np.array([]) for _ in range(multi_cam.num_cams)]

        camera_pair_list = list(combinations(np.arange(multi_cam.num_cams), 2))
        camera_pair_joint_view_count = [0 for _ in range(len(camera_pair_list))]
        each_cameras_shared_board_view_count_array = np.zeros((multi_cam.num_cams, multi_cam.num_cams))
        each_cameras_shared_board_view_count_total = np.zeros(multi_cam.num_cams)

        charuco_points_from_previous_frames = [[] for _ in range(multi_cam.num_cams)]

        multi_cam_queue_size_list = []

        # #set up plots
        # plt.ion()
        # fig = plt.figure()
        # ax_queue_size  = plt.subplot(121, title='Multi Camera - Queueue Size', xlabel='Frame# I guess/? Maybe Loop#/?', ylabel='Multi frames in queue')
        # ax_shared_views  = plt.subplot(122, title='Shared Charuco Board Views', xlabel='Frame#/?', ylabel='Number of shared views')

        # artist_for_queue_trace = ax_queue_size.plot(0)

        # artists_for_shared_view_traces_list = []
        # for this_cam_num in range(multi_cam.num_cams):
        #     artists_for_shared_view_traces_list.append(ax_shared_views.plot(0, label=f'Cam {this_cam_num}'))
        # ax_shared_views.legend()

        while not multi_cam.exit_event.is_set():
            if not multi_cam.multi_cam_tuple_queue.empty():

                this_multi_cam_tuple = multi_cam.multi_cam_tuple_queue.get()
                current_loop_count += 1

                # multi_cam.save_synchronized_videos(this_multi_cam_tuple)

                # this_multi_cam_image_raw = multi_cam.stitch_multicam_image(this_multi_cam_tuple)

                # if multi_cam._save_multi_cam_to_mp4:
                #     if multi_cam._output_multi_cam_video_object is None:
                #         multi_cam.initialize_multi_cam_output_video(this_multi_cam_image_raw)

                # multi_cam._output_multi_cam_video_object.write(this_multi_cam_image_raw)

                if multi_cam._save_each_cam_to_mp4:
                    if multi_cam._each_cam_video_writer_object_list is None:
                        multi_cam.initialize_each_cam_output_video(this_multi_cam_tuple)

                    for this_cam_num in range(multi_cam.num_cams):
                        multi_cam._each_cam_video_writer_object_list[this_cam_num].write(
                            this_multi_cam_tuple[this_cam_num][1])

                new_cam_image_list = []
                full_charuco_detected_on_this_frame = [False for _ in range(multi_cam.num_cams)]

                for this_cam_num in range(multi_cam.num_cams):
                    this_cam_tuple = this_multi_cam_tuple[this_cam_num]
                    this_cam_image = this_cam_tuple[1]

                    if current_loop_count % 10 == 0:
                        charuco_corners[this_cam_num], charuco_ids[this_cam_num], aruco_square_corners[this_cam_num], \
                        aruco_square_ids[this_cam_num] = detect_charuco_board(this_cam_image)

                    if len(charuco_ids[this_cam_num]) == num_charuco_corners:
                        full_charuco_detected_on_this_frame[this_cam_num] = True

                    # image_w_markers = cv2.aruco.drawDetectedMarkers(this_cam_image, aruco_square_corners[this_cam_num], aruco_square_ids[this_cam_num])

                    image_w_markers = cv2.aruco.drawDetectedCornersCharuco(this_cam_image,
                                                                           np.array(charuco_corners[this_cam_num]),
                                                                           np.array(charuco_ids[this_cam_num]))

                    this_cam_name = "Camera " + str(this_cam_num)

                    text_to_write_on_this_camera = ''
                    current_cam_corner_count_str = this_cam_name + ": " + str(
                        len(charuco_ids[this_cam_num])) + " of " + str(
                        num_charuco_corners) + " detected | Full Board: " + str(
                        full_charuco_detected_on_this_frame[this_cam_num])
                    this_cam_shared_views_str = " | Shared Views: " + str(
                        each_cameras_shared_board_view_count_total[this_cam_num])
                    text_to_write_on_this_camera = current_cam_corner_count_str + this_cam_shared_views_str

                    if this_cam_num == 0:
                        queue_size_str = "Multi-Camera Queue Size: " + str(multi_cam.multi_cam_tuple_queue.qsize())
                        queue_text_position = (10, 20)
                        cv2.putText(
                            image_w_markers,  # numpy array on which text is written
                            queue_size_str,  # text
                            queue_text_position,  # position at which writing has to start
                            cv2.FONT_HERSHEY_SIMPLEX,  # font family
                            .5,  # font size
                            (255, 10, 100, 255),  # font color
                            2)  # font stroke
                        cv2.putText(
                            image_w_markers,  # numpy array on which text is written
                            queue_size_str,  # text
                            queue_text_position,  # position at which writing has to start
                            cv2.FONT_HERSHEY_SIMPLEX,  # font family
                            .5,  # font size
                            (30, 10, 0, 255),  # font color
                            3)  # font stroke

                    position = (10, 50)
                    cv2.putText(
                        image_w_markers,  # numpy array on which text is written
                        text_to_write_on_this_camera,  # text
                        position,  # position at which writing has to start
                        cv2.FONT_HERSHEY_SIMPLEX,  # font family
                        .5,  # font size
                        (30, 10, 0, 255),  # font color
                        3)  # font stroke
                    cv2.putText(
                        image_w_markers,  # numpy array on which text is written
                        text_to_write_on_this_camera,  # text
                        position,  # position at which writing has to start
                        cv2.FONT_HERSHEY_SIMPLEX,  # font family
                        .5,  # font size
                        (209, 180, 0, 255),  # font color
                        1)  # font stroke

                    if full_charuco_detected_on_this_frame[this_cam_num]:
                        cv2.polylines(image_w_markers, np.int32([charuco_corners[this_cam_num]]), True, (0, 100, 255),
                                      2)
                        # for these_corners in charuco_points_from_previous_frames[this_cam_num]:
                        # if len(these_corners)>0:
                        #     cv2.polylines(image_w_markers, np.int32([these_corners[this_cam_num]]), True, (0,100,255,255/2), 2)

                    charuco_points_from_previous_frames[this_cam_num].append(charuco_corners[this_cam_num])

                    new_cam_image_list.append(this_cam_image)

                # determine paired board views
                for this_cam_num in range(multi_cam.num_cams):
                    if full_charuco_detected_on_this_frame[this_cam_num]:
                        for this_other_camera_num in range(multi_cam.num_cams):
                            if this_other_camera_num != this_cam_num:
                                if full_charuco_detected_on_this_frame[this_other_camera_num]:
                                    each_cameras_shared_board_view_count_array[this_cam_num, this_other_camera_num] += 1
                each_cameras_shared_board_view_count_total = np.sum(each_cameras_shared_board_view_count_array, axis=1)
                # print(each_cameras_shared_board_view_count)

                for this_pair_num, this_cam_pair in enumerate(camera_pair_list):
                    camera_one_id = this_cam_pair[0]
                    camera_two_id = this_cam_pair[1]

                    if full_charuco_detected_on_this_frame[camera_one_id] and full_charuco_detected_on_this_frame[
                        camera_two_id]:
                        camera_pair_joint_view_count[this_pair_num] += 1

                # update plots
                multi_cam_queue_size_list.append(multi_cam.multi_cam_tuple_queue.qsize())

                # artist_for_queue_trace[0].set_data((np.arange(current_loop_count),multi_cam_queue_size_list))
                # plt.pause(0.01)
                # plt.draw()
                # for camNum in range(multi_cam.num_cams):
                #     ax_shared_views.plot(0, label=f'Cam {camNum}')

                multi_cam_image = np.hstack(new_cam_image_list)

                cv2.imshow(multi_cam._rec_name, multi_cam_image)

                key = cv2.waitKey(1)

                if key == 27:  # exit on ESC
                    break

                if cv2.getWindowProperty(multi_cam._rec_name, cv2.WND_PROP_VISIBLE) < 1:  # break loop if window closed
                    break

        cv2.destroyAllWindows()

        if multi_cam._save_multi_cam_to_mp4:
            multi_cam._output_multi_cam_video_object.release()

        if multi_cam._save_each_cam_to_mp4:
            for this_cam_num in range(multi_cam.num_cams):
                multi_cam._each_cam_video_writer_object_list[this_cam_num].release()

        console.rule('Shutting down MultiCamera Viewer')
        multi_cam.exit_event.set()  # send the 'Exit' signal to everyone.


    except Exception:
        console.print_exception()
