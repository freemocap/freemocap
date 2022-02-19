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
            model_complexity=2,
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
