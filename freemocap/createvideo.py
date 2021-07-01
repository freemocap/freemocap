import glob
import cv2
from pathlib import Path
import os


def createVideo(session):

    vidSavePath = str(session.sessionPath/'{}_outVid.mp4'.format(session.sessionID))
    fps = 30
    shape = 1078,647
    frame_array = []

    for filename in session.imOutPath.glob('*.png'):
        filename= str(filename)

        #reading each files
        img = cv2.imread(filename)
        #resized = cv2.resize(img,shape)
        #shape = img.shape[:2]
        resized = cv2.resize(img,shape)
        #inserting the frames into an image array
        frame_array.append(resized)
    out = cv2.VideoWriter(vidSavePath,cv2.VideoWriter_fourcc(*'DIVX'), fps, shape)
    for i in range(len(frame_array)):
        # writing to a image array
        out.write(frame_array[i])
    out.release()


def createBodyTrackingVideos(session):

    vidSavePath = str(session.sessionPath/'{}_outVid.mp4'.format(session.sessionID))
    fps = 30
    shape = 1078,647
    #frame_array = []

    if session.useOpenPose:

        for count,videoPath in enumerate(session.session_settings['openPose_imgPathList']):
            frame_array = []
            vidSavePath = str(session.openPoseDataPath/'openPoseVideo_cam{}.mp4'.format(count))
            videoPath = Path(videoPath)
            for filename in videoPath.glob('*.png'):  
                
                filename= str(filename)
                #reading each files
                img = cv2.imread(filename)
                #resized = cv2.resize(img,shape)
                #shape = img.shape[:2]
                resized = cv2.resize(img,shape)
                #inserting the frames into an image array
                frame_array.append(resized)
            out = cv2.VideoWriter(vidSavePath,cv2.VideoWriter_fourcc(*'DIVX'), fps, shape)
            for i in range(len(frame_array)):
                # writing to a image array
                out.write(frame_array[i])
            out.release()