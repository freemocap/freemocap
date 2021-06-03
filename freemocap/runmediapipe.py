import os
from pathlib import Path
import glob
import json

import numpy as np
from rich.progress import track
from ruamel.yaml import YAML
import cv2
import h5py
import mediapipe as mp
from pathlib import Path
mp_drawing = mp.solutions.drawing_utils
mp_holistic = mp.solutions.holistic

def runMediaPipe(session, dummyRun=False):

    mediaPipe_jsonPathList = [] #list to hold the paths to the json files
    mediaPipe_imgPathList = []
    mediaPipe_imgPathList_yaml = []
    mediaPipe_jsonPathList_yaml = []
    
    with mp_holistic.Holistic() as holistic:
        eachCamerasData = [] #Create an empty list that holds each cameras data
        for thisVidPath in session.syncedVidPath.iterdir():  #Run MediaPipe 'Holistic' (body, hands, face) tracker on each video in the raw video folder
            if thisVidPath.suffix =='.mp4': #NOTE - at some point we should build some list of 'synced video names' and check against that 
                print('MediaPiping: ', thisVidPath.name )
                vidPath = session.mediaPipeDataPath / thisVidPath.stem
                jsonPath = vidPath / 'json'
                jsonPath.mkdir(parents=True, exist_ok=True) #this camera's json files (with keypoints)
                imgPath = vidPath / 'images'
                imgPath.mkdir(parents=True, exist_ok=True) 
                mediaPipe_jsonPathList.append(jsonPath)
                mediaPipe_imgPathList.append(imgPath)
                mediaPipe_imgPathList_yaml.append(str(imgPath))
                mediaPipe_jsonPathList_yaml.append(str(jsonPath))
                mediaPipe_dataList = [] #Create an empty list for mediapipes data
                if not dummyRun:
                    cap = cv2.VideoCapture(str(thisVidPath))
                    frameNum = -1
                    success, image = cap.read() #load first image from video
                    while success:
                        frameNum += 1
                        image_height, image_width, _ = image.shape
                        
                        results = holistic.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)) # THIS IS WHERE THE MAGIC HAPENS (ps. Convert the BGR image to RGB before processing.)
                        mediaPipe_dataList.append(results)#Append data to mediapipe data list 
                        
                        # Draw pose, left and right hands, and face landmarks on the image.
                        annotated_image = image.copy()
                        mp_drawing.draw_landmarks(
                            annotated_image, results.face_landmarks, mp_holistic.FACE_CONNECTIONS)
                        mp_drawing.draw_landmarks(
                            annotated_image, results.left_hand_landmarks, mp_holistic.HAND_CONNECTIONS)
                        mp_drawing.draw_landmarks(
                            annotated_image, results.right_hand_landmarks, mp_holistic.HAND_CONNECTIONS)
                        mp_drawing.draw_landmarks(
                            annotated_image, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS)

                        #save annotated image
                        frameName = str(frameNum).zfill(6)

                        cv2.imwrite(str(imgPath)+ '/' + frameName + '.png', annotated_image)
                        
                        #load the next image (will break `while-loop` on the last frame)
                        success, image = cap.read()#load next image from video    
                        f=9
                eachCamerasData.append(mediaPipe_dataList)#Append that cameras data for every frame to the camera datalist


    session.mediaPipe_jsonPathList = mediaPipe_jsonPathList
    session.mediaPipe_imgPathList = mediaPipe_imgPathList

    yaml = YAML()
    data = yaml.load(session.yamlPath)
    data['mediaPipe_imgPathList'] = mediaPipe_imgPathList_yaml
    data['mediaPipe_jsonPathList'] = mediaPipe_jsonPathList_yaml
    yaml.dump(data, session.yamlPath)
    session.mediaPipeData = eachCamerasData
   

def parseMediaPipe(session):
        numCams = len(session.mediaPipeData) #Get number of cameras
        numFrames = len(session.mediaPipeData[0]) #Get number of frames
        #numBodyPoints = len(np.max(session.mediaPipeData[0][:].pose_landmarks.landmark[:]))#Get number of body points
        #numFacePoints = len(np.max(session.mediaPipeData[0][:].face_landmarks.landmark[:]))#Get number of face points        
        #numLeftHandPoints = len(np.max(session.mediaPipeData[0][:].left_hand_landmarks.landmark[:]))#Get number of right hand points
        #numRightHandPoints = len(np.max(session.mediaPipeData[0][:].right_hand_landmarks.landmark[:]))#Get number of left hand points
        numBodyPoints = 33
        numFacePoints = 468
        numLeftHandPoints = 21
        numRightHandPoints = 21
        
        numPoints = numBodyPoints+numFacePoints+numLeftHandPoints+numRightHandPoints #Get total points
        mediaPipe_nCams_nFrames_nImgPts_XYC = np.ndarray((int(numCams),int(numFrames),int(numPoints),3)) #Create empty array the size of number of cams, frame, points, XYC
        for nn in range(numCams):#Loop through each camera
            for ii in range(numFrames): #Loop through each frame 
                for jj in range(numBodyPoints):
                    if  session.mediaPipeData[0][ii].pose_landmarks is None: #If that point is not detected
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj,0] = np.nan #Add nan value to that index
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj,1] = np.nan #Add nan value to that index
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj,2] = np.nan #Add nan value to that index
                    else:
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj,0] = session.mediaPipeData[0][ii].pose_landmarks.landmark[jj].x#Take x pos of that point
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj,1] = session.mediaPipeData[0][ii].pose_landmarks.landmark[jj].y#Take y pos of that point
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj,2] = session.mediaPipeData[0][ii].pose_landmarks.landmark[jj].visibility#Take visibility(confidence) pos of that point
                for jj in range(numFacePoints): 
                    if  session.mediaPipeData[0][ii].face_landmarks is None: #If that point is not detected
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints,0] = np.nan #Add nan value to that index
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints,1] = np.nan #Add nan value to that index
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints,2] = np.nan #Add nan value to that index
                    else:
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints,0] = session.mediaPipeData[0][ii].face_landmarks.landmark[jj].x#Take x pos of that point
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints,1] = session.mediaPipeData[0][ii].face_landmarks.landmark[jj].y#Take y pos of that point
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints,2] = session.mediaPipeData[0][ii].face_landmarks.landmark[jj].visibility#Take visibility(confidence) pos of that point
                for jj in range(numRightHandPoints): 
                    if  session.mediaPipeData[0][ii].right_hand_landmarks is None: #If that point is not detected
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints,0] = np.nan #Add nan value to that index
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints,1] = np.nan #Add nan value to that index
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints,2] = np.nan #Add nan value to that index
                    else:
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints,0] = session.mediaPipeData[0][ii].right_hand_landmarks.landmark[jj].x#Take x pos of that point
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints,1] = session.mediaPipeData[0][ii].right_hand_landmarks.landmark[jj].y#Take y pos of that point
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints,2] = session.mediaPipeData[0][ii].right_hand_landmarks.landmark[jj].visibility#Take visibility(confidence) pos of that point
                for jj in range(numLeftHandPoints): 
                    if  session.mediaPipeData[0][ii].left_hand_landmarks is None: #If that point is not detected
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints+numRightHandPoints,0] = np.nan #Add nan value to that index
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints+numRightHandPoints,1] = np.nan #Add nan value to that index
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints+numRightHandPoints,2] = np.nan #Add nan value to that index
                    else:
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints+numRightHandPoints,0] = session.mediaPipeData[0][ii].left_hand_landmarks.landmark[jj].x#Take x pos of that point
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints+numRightHandPoints,1] = session.mediaPipeData[0][ii].left_hand_landmarks.landmark[jj].y#Take y pos of that point
                        mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints+numRightHandPoints,2] = session.mediaPipeData[0][ii].left_hand_landmarks.landmark[jj].visibility#Take visibility(confidence) pos of that point
            #print(session.mediaPipe_datalist[0].pose_landmarks.landmark[0].x)

        path_to_mediapipe_2d = session.dataArrayPath/'mediaPipeData_nCams_nFrames_nImgPts_XY.npy'
        
        mediaPipeData_nCams_nFrames_nImgPts_XY =  mediaPipe_nCams_nFrames_nImgPts_XYC[:,:,:,0:2].copy()
        np.save(path_to_mediapipe_2d, mediaPipeData_nCams_nFrames_nImgPts_XY)
        
        



        return mediaPipeData_nCams_nFrames_nImgPts_XY