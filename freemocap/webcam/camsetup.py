import threading
import cv2
import imutils
import os
import platform
import time 

import mediapipe as mp
import numpy as np


mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
mp_holistic = mp.solutions.holistic

class VideoSetup(threading.Thread):
    """
    Class to run and thread webcams for preview purposes
    """
    def __init__(self, camID, parameterDictionary, rotNum):
        self.camID = camID
        self.parameterDictionary = parameterDictionary
        self.rotNum = rotNum
        threading.Thread.__init__(self)

    def run(self):
        # print("Starting " + self.previewName)
        self.record(self.parameterDictionary, self.rotNum)

    def record(self, parameterDictionary, rotNum):
        exposure = parameterDictionary.get("exposure")
        resWidth = parameterDictionary.get("resWidth")
        resHeight = parameterDictionary.get("resHeight")
        camWindowName = "Camera" + str(self.camID)+' Preview - Press ESC to exit Setup'
        cv2.namedWindow(camWindowName)

        if platform.system() == 'Windows':
            cap = cv2.VideoCapture(self.camID, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(self.camID, cv2.CAP_ANY)


        cap.set(cv2.CAP_PROP_FRAME_WIDTH, resWidth)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resHeight)
        cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')) 

        # showing values of the properties
        print("__________________________________________")
        print("cv2::videocapture properties for Camera# {}".format(self.camID))
        print("CV_CAP_PROP_FRAME_WIDTH: '{}'".format(cap.get(cv2.CAP_PROP_FRAME_WIDTH)))
        print("CV_CAP_PROP_FRAME_HEIGHT : '{}'".format(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        print("CAP_PROP_FPS : '{}'".format(cap.get(cv2.CAP_PROP_FPS)))
        print("CAP_PROP_EXPOSURE : '{}'".format(cap.get(cv2.CAP_PROP_EXPOSURE)))
        print("CAP_PROP_POS_MSEC : '{}'".format(cap.get(cv2.CAP_PROP_POS_MSEC)))
        print("CAP_PROP_FRAME_COUNT  : '{}'".format(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        print("CAP_PROP_BRIGHTNESS : '{}'".format(cap.get(cv2.CAP_PROP_BRIGHTNESS)))
        print("CAP_PROP_CONTRAST : '{}'".format(cap.get(cv2.CAP_PROP_CONTRAST)))
        print("CAP_PROP_SATURATION : '{}'".format(cap.get(cv2.CAP_PROP_SATURATION)))
        print("CAP_PROP_HUE : '{}'".format(cap.get(cv2.CAP_PROP_HUE)))
        print("CAP_PROP_GAIN  : '{}'".format(cap.get(cv2.CAP_PROP_GAIN)))
        print("CAP_PROP_CONVERT_RGB : '{}'".format(cap.get(cv2.CAP_PROP_CONVERT_RGB)))
        print("__________________________________________")

        while True:
            ret1, frame1 = cap.read()
            charuco_corners, charuco_ids, aruco_square_corners, aruco_square_ids = detect_charuco_board(frame1)
            annotate_image_with_charuco_data(frame1, charuco_corners, charuco_ids)
            
            if ret1 == True:
                if rotNum is not None:
                    frame1 = imutils.rotate_bound(frame1, angle=rotNum)
                
                cv2.imshow(camWindowName, frame1)
                if cv2.waitKey(1) & 0xFF == 27:
                    # == ord('q') for q
                    break

            else:
                break
        cv2.destroyWindow(camWindowName)

class MediaPipeVideoSetup(threading.Thread):
    """
    Class to run and thread webcams for preview purposes
    """
    def __init__(self, camID, parameterDictionary, rotNum):
        self.camID = camID
        self.parameterDictionary = parameterDictionary
        self.rotNum = rotNum
        threading.Thread.__init__(self)

    def run(self):
        # print("Starting " + self.previewName)
        self.record(self.parameterDictionary, self.rotNum)

    def record(self, parameterDictionary, rotNum):
        exposure = parameterDictionary.get("exposure")
        resWidth = parameterDictionary.get("resWidth")
        resHeight = parameterDictionary.get("resHeight")
        camWindowName = "RECORDING - Camera" + str(self.camID)+' - Press ESC to exit'

        cv2.namedWindow(camWindowName)

        if platform.system() == 'Windows':
            cap = cv2.VideoCapture(self.camID, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(self.camID, cv2.CAP_ANY)

        with mp_holistic.Holistic(
            static_image_mode=False,
            model_complexity=0,
            enable_segmentation=True) as holistic:

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, resWidth)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resHeight)
            cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')) 

                # showing values of the properties
            print("__________________________________________")
            print("cv2::videocapture properties for Camera# {}".format(self.camID))
            print("CV_CAP_PROP_FRAME_WIDTH: '{}'".format(cap.get(cv2.CAP_PROP_FRAME_WIDTH)))
            print("CV_CAP_PROP_FRAME_HEIGHT : '{}'".format(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            print("CAP_PROP_FPS : '{}'".format(cap.get(cv2.CAP_PROP_FPS)))
            print("CAP_PROP_EXPOSURE : '{}'".format(cap.get(cv2.CAP_PROP_EXPOSURE)))
            print("CAP_PROP_POS_MSEC : '{}'".format(cap.get(cv2.CAP_PROP_POS_MSEC)))
            print("CAP_PROP_FRAME_COUNT  : '{}'".format(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
            print("CAP_PROP_BRIGHTNESS : '{}'".format(cap.get(cv2.CAP_PROP_BRIGHTNESS)))
            print("CAP_PROP_CONTRAST : '{}'".format(cap.get(cv2.CAP_PROP_CONTRAST)))
            print("CAP_PROP_SATURATION : '{}'".format(cap.get(cv2.CAP_PROP_SATURATION)))
            print("CAP_PROP_HUE : '{}'".format(cap.get(cv2.CAP_PROP_HUE)))
            print("CAP_PROP_GAIN  : '{}'".format(cap.get(cv2.CAP_PROP_GAIN)))
            print("CAP_PROP_CONVERT_RGB : '{}'".format(cap.get(cv2.CAP_PROP_CONVERT_RGB)))
            print("__________________________________________")
            timestamps = []
            while True:
                ret1, frame1 = cap.read()
                timestamps.append(time.time())
                
                print(f"mean fps for cam {self.camID} is {1/np.mean(np.diff(timestamps))}")
                
                if ret1 == True:

                    charuco_corners, charuco_ids, aruco_square_corners, aruco_square_ids = detect_charuco_board(frame1)
                    try:
                        results = holistic.process(cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB))
                    except Exception as e:
                        print(e)
                
                    annotate_image_with_charuco_data(frame1, charuco_corners, charuco_ids)
        
                    frame1.flags.writeable = False
                    try:
                        results = holistic.process(cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB))
                    except Exception as e:
                        print(e)
                    mp_drawing.draw_landmarks(
                        frame1,
                        results.face_landmarks,
                        mp_holistic.FACEMESH_CONTOURS,
                        landmark_drawing_spec=None,
                        connection_drawing_spec=mp_drawing_styles
                        .get_default_face_mesh_contours_style())
                    mp_drawing.draw_landmarks(
                        frame1,
                        results.pose_landmarks,
                        mp_holistic.POSE_CONNECTIONS,
                        landmark_drawing_spec=mp_drawing_styles
                        .get_default_pose_landmarks_style())
                    mp_drawing.draw_landmarks(
                        frame1,
                        results.left_hand_landmarks,
                        mp_holistic.HAND_CONNECTIONS,
                        landmark_drawing_spec=mp_drawing_styles
                        .get_default_hand_landmarks_style())
                    mp_drawing.draw_landmarks(
                        frame1,
                        results.right_hand_landmarks,
                        mp_holistic.HAND_CONNECTIONS,
                        landmark_drawing_spec=mp_drawing_styles
                        .get_default_hand_landmarks_style())
                    if rotNum is not None:
                        frame1 = imutils.rotate_bound(frame1, angle=rotNum)
                        
                        
                    
                    
                    cv2.imshow(camWindowName, frame1)
                    if cv2.waitKey(1) & 0xFF == 27:
                        # == ord('q') for q
                        break

                else:
                    break
            cv2.destroyWindow(camWindowName)



def RunSetup(cam_inputs, rotation_input, paramDict,mediaPipeOverlay):
    """
    Start video setup by threading instances of the VideoSetup class
    """
    if not cam_inputs:
        raise ValueError("Camera input list (cam_inputs) is empty")

    ulist = []

    for cam_input, cam_rotation in zip(cam_inputs, rotation_input):
        if mediaPipeOverlay == True:
            u = MediaPipeVideoSetup(cam_input, paramDict, cam_rotation)
        else:
            u = VideoSetup(cam_input, paramDict, cam_rotation)
        u.start()
        ulist.append(u)

    for k in ulist:
        k.join()





def detect_charuco_board(image,  annotate_image=True):
    """
    Charuco base pose estimation.
    more-or-less copied from - https://mecaruco2.readthedocs.io/en/latest/notebooks_rst/Aruco
    /sandbox/ludovic/aruco_calibration_rotation.html
    """
    charuco_corners = []
    charuco_ids = []
    
    aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_250)
    charuco_length = 7
    charuco_width = 5

    board = cv2.aruco.CharucoBoard_create(charuco_length, charuco_width, 1, .8, aruco_dict)
    global num_charuco_corners
    num_charuco_corners = (charuco_length-1) * (charuco_width-1)


    # SUB PIXEL CORNER DETECTION CRITERION
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.00001)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    aruco_square_corners, aruco_square_ids, rejectedImgPoints = cv2.aruco.detectMarkers(gray,
        aruco_dict)

    if len(aruco_square_corners) > 0:
        # SUB PIXEL DETECTION
        for this_corner in aruco_square_corners:
            cv2.cornerSubPix(gray, this_corner,
                winSize=(3, 3),
                zeroZone=(-1, -1),
                criteria=criteria)
        res2 = cv2.aruco.interpolateCornersCharuco(aruco_square_corners, aruco_square_ids, gray,
            board)

        if res2[1] is not None and res2[2] is not None and len(res2[1]) > 3:
            charuco_corners = res2[1]
            charuco_ids = res2[2]


    return charuco_corners, charuco_ids, aruco_square_corners, aruco_square_ids

def annotate_image_with_charuco_data(image, charuco_corners, charuco_ids)->bool:

    full_charuco_detected_on_this_frame = False
    if len(charuco_ids) == num_charuco_corners:
        full_charuco_detected_on_this_frame = True

    image_w_markers = cv2.aruco.drawDetectedCornersCharuco(image,
                                                            np.array(charuco_corners),
                                                            np.array(charuco_ids),
                                                            (200,100,200,255)) #I think cv2 uses BGR instead of RGB?


    text_to_write_on_this_camera = ''
    current_cam_corner_count_str = str(
        len(charuco_ids)) + " of " + str(
        num_charuco_corners) + " ChAruco Corner Points detected | Full Board Detected: " + str(
        full_charuco_detected_on_this_frame)
    # TODO - Determine 'shared views' (i.e. frames in which a full board is detected by 2 cameras)
    # TODO - self.determine_shared_charuco_board_views()
    # this_cam_shared_views_str = " | Shared Views: " + str(
    #     each_cameras_shared_board_view_count_total)
    text_to_write_on_this_camera = current_cam_corner_count_str

    position = (10, 50)
    cv2.putText(
        image_w_markers,  # numpy array on which text is written
        text_to_write_on_this_camera,  # text
        position,  # position at which writing has to start
        cv2.FONT_HERSHEY_SIMPLEX,  # font family
        .5,  # font size
        (0, 10, 0, 255),  # font color
        4)  # font stroke (draw a darker heavier font beneath a lighter/thinner copy for readability)

    cv2.putText(
        image_w_markers,  # numpy array on which text is written
        text_to_write_on_this_camera,  # text
        position,  # position at which writing has to start
        cv2.FONT_HERSHEY_SIMPLEX,  # font family (very limited selection, i think there's some interesting CV history here...)
        .5,  # font size
        (209, 180, 0, 255),  # font color
        2 ) # font stroke

    if full_charuco_detected_on_this_frame:
        cv2.polylines(image_w_markers, np.int32([charuco_corners]), True, (0, 255, 255), 4)
        # for these_corners in charuco_points_from_previous_frames:
        # if len(these_corners)>0:
        #     cv2.polylines(image_w_markers, np.int32([these_corners]), True, (0,100,255,255/2), 2)

    return True