from pathlib import Path


import numpy as np
from rich.progress import Progress
from ruamel.yaml import YAML
import cv2
import mediapipe as mp
# from numba import jit

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
                    numFrames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    success, image = cap.read() #load first image from video

                    with Progress() as progress:
                        progressBar = progress.add_task('[magenta]MediaPiping: {}'.format(thisVidPath.name), total=numFrames) #make progressbar

                        while success:
                            
                            if frameNum%5==0:
                                progress.update(progressBar, advance=5) #increment progress bar everyh 5th frame

                            frameNum += 1

                            image_height, image_width, _ = image.shape
                            
                            results = holistic.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)) # THIS IS WHERE THE MAGIC HAPENS (ps. Convert the BGR image to RGB before processing.)
                            
                            try:
                                results.pose_landmarks.landmark 
                                try:
                                    results.left_hand_landmarks.landmark 
                                    try:
                                        results.right_hand_landmarks.landmark 
                                        try:
                                            results.face_landmarks.landmark
                                            f=9
                                        except:
                                            pass
                                    except:
                                        pass
                                except:
                                    pass
                            except:
                                pass

                            mediaPipe_dataList.append(results)#Append data to mediapipe data list 
                            

                            saveImages = True
                            if saveImages:
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

    session.image_height = image_height
    session.image_width = image_width
    
    session.mediaPipe_jsonPathList = mediaPipe_jsonPathList
    session.mediaPipe_imgPathList = mediaPipe_imgPathList

    yaml = YAML()
    data = yaml.load(session.yamlPath)
    data['mediaPipe_imgPathList'] = mediaPipe_imgPathList_yaml
    data['mediaPipe_jsonPathList'] = mediaPipe_jsonPathList_yaml
    yaml.dump(data, session.yamlPath)
    session.mediaPipeData = eachCamerasData
   
# @jit(nopython=True)
def parseMediaPipe(session):
        numCams = len(session.mediaPipeData) #Get number of cameras
        numFrames = len(session.mediaPipeData[0]) #Get number of frames
        #numBodyPoints = len(np.max(session.mediaPipeData[0][:].pose_landmarks.landmark[:]))#Get number of body points
        #numFacePoints = len(np.max(session.mediaPipeData[0][:].face_landmarks.landmark[:]))#Get number of face points        
        #numLeftHandPoints = len(np.max(session.mediaPipeData[0][:].left_hand_landmarks.landmark[:]))#Get number of right hand points
        #numRightHandPoints = len(np.max(session.mediaPipeData[0][:].right_hand_landmarks.landmark[:]))#Get number of left hand points
        numBodyPoints = 33
        numFacePoints = 468
        numHandPoints = 21
        
        numTrackedPoints = numBodyPoints+numHandPoints*2+numFacePoints #Get total points

        #Create  array of nans the size of number of cams, frame, points, XYC
        mediaPipeData_nCams_nFrames_nImgPts_XYC = np.empty((int(numCams),int(numFrames),int(numTrackedPoints),3))  # create empty array 
        mediaPipeData_nCams_nFrames_nImgPts_XYC[:] = np.NaN #Fill it with NaNs!

        for camNum in range(numCams):#Loop through each camera
            for frNum in range(numFrames): #Loop through each frame 
                # make empty arrays for thisFrame's data
                thisFrame_X = np.empty(numTrackedPoints)
                thisFrame_X[:] = np.nan
                thisFrame_Y  = thisFrame_X.copy()
                thisFrame_C  = thisFrame_X.copy()

                fullFrame = True
                if frNum == 107:
                    f=9
                try:
                    #pull out ThisFrame's mediapipe data (`mpData.pose_landmarks.landmark` returns something iterable ¯\_(ツ)_/¯)
                    thisFrame_poseDataLandMarks = session.mediaPipeData[camNum][frNum].pose_landmarks.landmark # body ('pose') data
                    #stuff body data into pre-allocated nan array
                    thisFrame_X[:numBodyPoints] = [pp.x for pp in thisFrame_poseDataLandMarks] #PoseX data - Normalized screen coords (in range [0, 1]) - need multiply by image resultion for pixels
                    thisFrame_Y[:numBodyPoints] = [pp.y for pp in thisFrame_poseDataLandMarks] #PoseY data
                    thisFrame_C[:numBodyPoints] = [pp.visibility for pp in thisFrame_poseDataLandMarks] #'visibility' is MediaPose's 'confidence' measure in range [0,1]
                except:
                    fullFrame = False


                # Right hand data
                try:
                    thisFrame_rHandDataLandMarks = session.mediaPipeData[camNum][frNum].right_hand_landmarks.landmark #right hand data
                    thisFrame_X[numBodyPoints+1:numBodyPoints+1+numHandPoints] = [pp.x for pp in thisFrame_rHandDataLandMarks] #PoseX data - Normalized screen coords (in range [0, 1]) - need multiply by image resultion for pixels
                    thisFrame_Y[numBodyPoints+1:numBodyPoints+1+numHandPoints] = [pp.y for pp in thisFrame_rHandDataLandMarks] #PoseY data
                    thisFrame_C[numBodyPoints+1:numBodyPoints+1+numHandPoints] = [pp.visibility for pp in thisFrame_rHandDataLandMarks] #'visibility' is MediaPose's 'confidence' measure in range [0,1]
                except:
                    fullFrame = False

                # Left hand data
                try:
                    thisFrame_lHandDataLandMarks = session.mediaPipeData[camNum][frNum].left_hand_landmarks.landmark #left hand data
                    thisFrame_X[numBodyPoints+numHandPoints+1:numBodyPoints+1+numHandPoints*2] = [pp.x for pp in thisFrame_lHandDataLandMarks] #PoseX data - Normalized screen coords (in range [0, 1]) - need multiply by image resultion for pixels
                    thisFrame_Y[numBodyPoints+numHandPoints+1:numBodyPoints+1+numHandPoints*2] = [pp.y for pp in thisFrame_lHandDataLandMarks] #PoseY data
                    thisFrame_C[numBodyPoints+numHandPoints+1:numBodyPoints+1+numHandPoints*2] = [pp.visibility for pp in thisFrame_lHandDataLandMarks] #'visibility' is MediaPose's 'confidence' measure in range [0,1]
                except:
                    fullFrame = False

                #FaceMeshData
                try:
                    thisFrame_faceDataLandMarks = session.mediaPipeData[camNum][frNum].face_landmarks.landmark # face (mesh) data
                    thisFrame_X[numBodyPoints+numHandPoints*2+1:-1] = [pp.x for pp in thisFrame_faceDataLandMarks] #PoseX data - Normalized screen coords (in range [0, 1]) - need multiply by image resultion for pixels
                    thisFrame_Y[numBodyPoints+numHandPoints*2:-1] = [pp.y for pp in thisFrame_faceDataLandMarks] #PoseY data
                    #NOTE - There's also Z data in here
                    thisFrame_C[numBodyPoints+numHandPoints*2:-1] = [pp.visibility for pp in thisFrame_faceDataLandMarks] #'visibility' is MediaPose's 'confidence' measure in range [0,1]
                except:
                    fullFrame = False

                if fullFrame:
                    f=9
                    
                #stuff this frame's data into pre-allocated mediaPipeData_.... array
                mediaPipeData_nCams_nFrames_nImgPts_XYC[camNum,frNum,:,0] = thisFrame_X
                mediaPipeData_nCams_nFrames_nImgPts_XYC[camNum,frNum,:,1] = thisFrame_Y
                mediaPipeData_nCams_nFrames_nImgPts_XYC[camNum,frNum,:,2] = thisFrame_C


        #convert from normalized screen coordinates to pixel coordinates
        mediaPipeData_nCams_nFrames_nImgPts_XYC[:,:,:,0] *=  session.image_height
        mediaPipeData_nCams_nFrames_nImgPts_XYC[:,:,:,1] *=  session.image_width

        np.save(session.dataArrayPath/'mediaPipe_2d.npy', mediaPipeData_nCams_nFrames_nImgPts_XYC)
        
        

        return mediaPipeData_nCams_nFrames_nImgPts_XYC