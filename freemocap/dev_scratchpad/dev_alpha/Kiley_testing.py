import cv2
import numpy as np
import mediapipe as mp
import math

cap = cv2.VideoCapture('C:/Users/kiley/Desktop/Mediapipe_Output_Videos/Processed_Video_2.avi')

def count_frames(cap):
    nframe = 0
    while True:
        (grabbed, frame) = cap.read()
        if not grabbed:
            break
        nframe += 1
    print(nframe)
    return nframe

nframe = count_frames(cap)

nFrames_nImgPts_XY = np.empty((nframe*14, 4), float) #there are 14 COM points to plot, and 4 columns


