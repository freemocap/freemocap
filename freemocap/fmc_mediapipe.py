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

    session.mediaPipeDataPath.mkdir(exist_ok = True)

    mediaPipe_jsonPathList = []  # list to hold the paths to the json files
    mediaPipe_imgPathList = []
    mediaPipe_imgPathList_yaml = []
    mediaPipe_jsonPathList_yaml = []

    with mp_holistic.Holistic() as holistic:
        eachCamerasData = []  # Create an empty list that holds each cameras data
        for (
            thisVidPath
        ) in (
            session.syncedVidPath.iterdir()
        ):  # Run MediaPipe 'Holistic' (body, hands, face) tracker on each video in the raw video folder
            if (
                thisVidPath.suffix == ".mp4"
            ):  # NOTE - at some point we should build some list of 'synced video names' and check against that

                vidPath = session.mediaPipeDataPath / thisVidPath.stem
                jsonPath = vidPath / "json"
                jsonPath.mkdir(
                    parents=True, exist_ok=True
                )  # this camera's json files (with keypoints)
                imgPath = vidPath / "images"
                imgPath.mkdir(parents=True, exist_ok=True)
                mediaPipe_jsonPathList.append(jsonPath)
                mediaPipe_imgPathList.append(imgPath)
                mediaPipe_imgPathList_yaml.append(str(imgPath))
                mediaPipe_jsonPathList_yaml.append(str(jsonPath))
                mediaPipe_dataList = []  # Create an empty list for mediapipes data
                if not dummyRun:
                    cap = cv2.VideoCapture(str(thisVidPath))

                    frameNum = -1
                    numFrames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    success, image = cap.read()  # load first image from video

                    with Progress() as progress:
                        progressBar = progress.add_task(
                            "[magenta]MediaPiping: {}".format(thisVidPath.name),
                            total=numFrames,
                        )  # make progressbar

                        while success:

                            if frameNum % 5 == 0:
                                progress.update(
                                    progressBar, advance=5
                                )  # increment progress bar everyh 5th frame

                            frameNum += 1

                            image_height, image_width, _ = image.shape

                            results = holistic.process(
                                cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                            )  # THIS IS WHERE THE MAGIC HAPENS (ps. Convert the BGR image to RGB before processing.)

                            try:
                                results.pose_landmarks.landmark
                                try:
                                    results.left_hand_landmarks.landmark
                                    try:
                                        results.right_hand_landmarks.landmark
                                        try:
                                            results.face_landmarks.landmark
                                            f = 9
                                        except:
                                            pass
                                    except:
                                        pass
                                except:
                                    pass
                            except:
                                pass

                            mediaPipe_dataList.append(
                                results
                            )  # Append data to mediapipe data list

                            saveImages = True
                            if saveImages:
                                # Draw pose, left and right hands, and face landmarks on the image.
                                annotated_image = image.copy()
                                mp_drawing.draw_landmarks(
                                    annotated_image,
                                    results.face_landmarks,
                                    mp_holistic.FACE_CONNECTIONS,
                                )
                                mp_drawing.draw_landmarks(
                                    annotated_image,
                                    results.left_hand_landmarks,
                                    mp_holistic.HAND_CONNECTIONS,
                                )
                                mp_drawing.draw_landmarks(
                                    annotated_image,
                                    results.right_hand_landmarks,
                                    mp_holistic.HAND_CONNECTIONS,
                                )
                                mp_drawing.draw_landmarks(
                                    annotated_image,
                                    results.pose_landmarks,
                                    mp_holistic.POSE_CONNECTIONS,
                                )

                                # save annotated image
                                frameName = str(frameNum).zfill(6)

                                cv2.imwrite(
                                    str(imgPath) + "/" + frameName + ".png",
                                    annotated_image,
                                )

                            # load the next image (will break `while-loop` on the last frame)
                            success, image = cap.read()  # load next image from video
                            f = 9
                eachCamerasData.append(
                    mediaPipe_dataList
                )  # Append that cameras data for every frame to the camera datalist

    session.image_height = image_height
    session.image_width = image_width

    session.mediaPipe_jsonPathList = mediaPipe_jsonPathList
    session.mediaPipe_imgPathList = mediaPipe_imgPathList

    session.session_settings['mediaPipe_imgPathList'] = str(mediaPipe_imgPathList)
    session.session_settings['mediaPipe_jsonPathList'] = str(mediaPipe_jsonPathList)

    #yaml = YAML()
    #data = yaml.load(session.yamlPath)
    #data["mediaPipe_imgPathList"] = mediaPipe_imgPathList_yaml
    #data["mediaPipe_jsonPathList"] = mediaPipe_jsonPathList_yaml
    #yaml.dump(data, session.yamlPath)
    session.mediaPipeData = eachCamerasData



def parseMediaPipe(session):
    numCams = len(session.mediaPipeData)  # Get number of cameras
    numFrames = len(session.mediaPipeData[0])  # Get number of frames
    # numBodyPoints = len(np.max(session.mediaPipeData[0][:].pose_landmarks.landmark[:]))#Get number of body points
    # numFacePoints = len(np.max(session.mediaPipeData[0][:].face_landmarks.landmark[:]))#Get number of face points
    # numLeftHandPoints = len(np.max(session.mediaPipeData[0][:].left_hand_landmarks.landmark[:]))#Get number of right hand points
    # numRightHandPoints = len(np.max(session.mediaPipeData[0][:].right_hand_landmarks.landmark[:]))#Get number of left hand points
    numBodyPoints = 33
    numFacePoints = 468
    numHandPoints = 21

    numTrackedPoints = (
        numBodyPoints + numHandPoints * 2 + numFacePoints
    )  # Get total points

    # Create  array of nans the size of number of cams, frame, points, XYC
    mediaPipeData_nCams_nFrames_nImgPts_XYC = np.empty(
        (int(numCams), int(numFrames), int(numTrackedPoints), 3)
    )  # create empty array
    mediaPipeData_nCams_nFrames_nImgPts_XYC[:] = np.NaN  # Fill it with NaNs!

    for camNum in range(numCams):  # Loop through each camera
        for frNum in range(numFrames):  # Loop through each frame
            # make empty arrays for thisFrame's data
            # thisFrame_X = np.empty(numTrackedPoints)
            # thisFrame_X[:] = np.nan
            # thisFrame_Y = thisFrame_X.copy()
            # thisFrame_C = thisFrame_X.copy()

            thisFrame_X_body = np.empty(numBodyPoints)
            thisFrame_X_body[:] = np.nan
            thisFrame_Y_body = thisFrame_X_body.copy()
            thisFrame_C_body = thisFrame_X_body.copy()

            thisFrame_X_face = np.empty(numFacePoints)
            thisFrame_X_face[:] = np.nan
            thisFrame_Y_face = thisFrame_X_face.copy()
            thisFrame_C_face = thisFrame_X_face.copy()

            thisFrame_hands = np.empty(numHandPoints)
            thisFrame_hands[:]= np.nan

            thisFrame_X_lefthand = thisFrame_hands.copy()
            thisFrame_Y_lefthand = thisFrame_hands.copy()
            thisFrame_C_lefthand = thisFrame_hands.copy()

            thisFrame_X_righthand = thisFrame_hands.copy()
            thisFrame_Y_righthand = thisFrame_hands.copy()
            thisFrame_C_righthand = thisFrame_hands.copy()

            fullFrame = True
            if frNum == 107:
                f = 9
            try:
                # pull out ThisFrame's mediapipe data (`mpData.pose_landmarks.landmark` returns something iterable ¯\_(ツ)_/¯)
                thisFrame_poseDataLandMarks = session.mediaPipeData[camNum][
                    frNum
                ].pose_landmarks.landmark  # body ('pose') data
                # stuff body data into pre-allocated nan array
                thisFrame_X_body[:numBodyPoints] = [
                    pp.x for pp in thisFrame_poseDataLandMarks
                ]  # PoseX data - Normalized screen coords (in range [0, 1]) - need multiply by image resultion for pixels
                thisFrame_Y_body[:numBodyPoints] = [
                    pp.y for pp in thisFrame_poseDataLandMarks
                ]  # PoseY data
                thisFrame_C_body[:numBodyPoints] = [
                    pp.visibility for pp in thisFrame_poseDataLandMarks
                ]  #'visibility' is MediaPose's 'confidence' measure in range [0,1]
            except:
                fullFrame = False

            # Right hand data
            try:
                thisFrame_rHandDataLandMarks = session.mediaPipeData[camNum][
                    frNum
                ].right_hand_landmarks.landmark  # right hand data
                thisFrame_X_righthand[:numHandPoints] = [
                    pp.x for pp in thisFrame_rHandDataLandMarks
                ]  # PoseX data - Normalized screen coords (in range [0, 1]) - need multiply by image resultion for pixels
                thisFrame_Y_righthand[:numHandPoints] = [
                    pp.y for pp in thisFrame_rHandDataLandMarks
                ]  # PoseY data
                thisFrame_C_righthand[:numHandPoints] = [
                    pp.visibility for pp in thisFrame_rHandDataLandMarks
                ]  #'visibility' is MediaPose's 'confidence' measure in range [0,1]
            except:
                fullFrame = False

            # Left hand data
            try:
                thisFrame_lHandDataLandMarks = session.mediaPipeData[camNum][
                    frNum
                ].left_hand_landmarks.landmark  # left hand data
                thisFrame_X_lefthand[:numHandPoints ] = [
                    pp.x for pp in thisFrame_lHandDataLandMarks
                ]  # PoseX data - Normalized screen coords (in range [0, 1]) - need multiply by image resultion for pixels
                thisFrame_Y_lefthand[:numHandPoints] = [
                    pp.y for pp in thisFrame_lHandDataLandMarks
                ]  # PoseY data
                thisFrame_C_lefthand[:numHandPoints] = [
                    pp.visibility for pp in thisFrame_lHandDataLandMarks
                ]  #'visibility' is MediaPose's 'confidence' measure in range [0,1]
            except:
                fullFrame = False

            # FaceMeshData
            try:
                thisFrame_faceDataLandMarks = session.mediaPipeData[camNum][
                    frNum
                ].face_landmarks.landmark  # face (mesh) data
                thisFrame_X_face[:numFacePoints] = [
                    pp.x for pp in thisFrame_faceDataLandMarks
                ]  # PoseX data - Normalized screen coords (in range [0, 1]) - need multiply by image resultion for pixels
                thisFrame_Y_face[:numFacePoints] = [
                    pp.y for pp in thisFrame_faceDataLandMarks
                ]  # PoseY data
                # NOTE - There's also Z data in here
                thisFrame_C_face[:numFacePoints] = [
                    pp.visibility for pp in thisFrame_faceDataLandMarks
                ]  #'visibility' is MediaPose's 'confidence' measure in range [0,1]
            except:
                fullFrame = False

            if fullFrame:
                f = 9

            thisFrame_X = np.concatenate((thisFrame_X_body,thisFrame_X_righthand,thisFrame_X_lefthand,thisFrame_X_face))
            thisFrame_Y = np.concatenate((thisFrame_Y_body,thisFrame_Y_righthand,thisFrame_Y_lefthand,thisFrame_Y_face))
            thisFrame_C = np.concatenate((thisFrame_C_body,thisFrame_C_righthand,thisFrame_C_lefthand,thisFrame_C_face))
            # stuff this frame's data into pre-allocated mediaPipeData_.... array
            mediaPipeData_nCams_nFrames_nImgPts_XYC[camNum, frNum, :, 0] = thisFrame_X
            mediaPipeData_nCams_nFrames_nImgPts_XYC[camNum, frNum, :, 1] = thisFrame_Y
            mediaPipeData_nCams_nFrames_nImgPts_XYC[camNum, frNum, :, 2] = thisFrame_C

    # convert from normalized screen coordinates to pixel coordinates
    mediaPipeData_nCams_nFrames_nImgPts_XYC[:, :, :, 0] *= session.image_width
    mediaPipeData_nCams_nFrames_nImgPts_XYC[:, :, :, 1] *= session.image_height
    mediaPipeData_nCams_nFrames_nImgPts_XYC[:, :, 34:, 2] = 1

    np.save(
        session.dataArrayPath / "mediaPipe_2d.npy",
        mediaPipeData_nCams_nFrames_nImgPts_XYC,
    )

    return mediaPipeData_nCams_nFrames_nImgPts_XYC
# #def parseMediaPipe2(session):

#         #numCams = len(session.mediaPipeData) #Get number of cameras
#         #numFrames = len(session.mediaPipeData[0]) #Get number of frames
#         #numBodyPoints = len(np.max(session.mediaPipeData[0][:].pose_landmarks.landmark[:]))#Get number of body points
#         #numFacePoints = len(np.max(session.mediaPipeData[0][:].face_landmarks.landmark[:]))#Get number of face points        
#         #numLeftHandPoints = len(np.max(session.mediaPipeData[0][:].left_hand_landmarks.landmark[:]))#Get number of right hand points
#         #numRightHandPoints = len(np.max(session.mediaPipeData[0][:].right_hand_landmarks.landmark[:]))#Get number of left hand points
#         numBodyPoints = 33
#         numFacePoints = 468
#         numLeftHandPoints = 21
#         numRightHandPoints = 21
        
#         numPoints = numBodyPoints+numFacePoints+numLeftHandPoints+numRightHandPoints #Get total points
#         mediaPipe_nCams_nFrames_nImgPts_XYC = np.ndarray((int(session.numCams),int(session.numFrames),int(numPoints),3)) #Create empty array the size of number of cams, frame, points, XYC
#         for nn in range(session.numCams):#Loop through each camera
#             for ii in range(session.numFrames): #Loop through each frame 
#                 for jj in range(numBodyPoints):
#                     if  session.mediaPipeData[0][ii].pose_landmarks is None: #If that point is not detected
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj,0] = np.nan #Add nan value to that index
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj,1] = np.nan #Add nan value to that index
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj,2] = np.nan #Add nan value to that index
#                     else:
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj,0] = session.mediaPipeData[0][ii].pose_landmarks.landmark[jj].x#Take x pos of that point
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj,1] = session.mediaPipeData[0][ii].pose_landmarks.landmark[jj].y#Take y pos of that point
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj,2] = session.mediaPipeData[0][ii].pose_landmarks.landmark[jj].visibility#Take visibility(confidence) pos of that point
#                 for jj in range(numFacePoints): 
#                     if  session.mediaPipeData[0][ii].face_landmarks is None: #If that point is not detected
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints,0] = np.nan #Add nan value to that index
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints,1] = np.nan #Add nan value to that index
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints,2] = np.nan #Add nan value to that index
#                     else:
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints,0] = session.mediaPipeData[0][ii].face_landmarks.landmark[jj].x#Take x pos of that point
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints,1] = session.mediaPipeData[0][ii].face_landmarks.landmark[jj].y#Take y pos of that point
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints,2] = session.mediaPipeData[0][ii].face_landmarks.landmark[jj].visibility#Take visibility(confidence) pos of that point
#                 for jj in range(numRightHandPoints): 
#                     if  session.mediaPipeData[0][ii].right_hand_landmarks is None: #If that point is not detected
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints,0] = np.nan #Add nan value to that index
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints,1] = np.nan #Add nan value to that index
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints,2] = np.nan #Add nan value to that index
#                     else:
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints,0] = session.mediaPipeData[0][ii].right_hand_landmarks.landmark[jj].x#Take x pos of that point
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints,1] = session.mediaPipeData[0][ii].right_hand_landmarks.landmark[jj].y#Take y pos of that point
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints,2] = session.mediaPipeData[0][ii].right_hand_landmarks.landmark[jj].visibility#Take visibility(confidence) pos of that point
#                 for jj in range(numLeftHandPoints): 
#                     if  session.mediaPipeData[0][ii].left_hand_landmarks is None: #If that point is not detected
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints+numRightHandPoints,0] = np.nan #Add nan value to that index
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints+numRightHandPoints,1] = np.nan #Add nan value to that index
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints+numRightHandPoints,2] = np.nan #Add nan value to that index
#                     else:
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints+numRightHandPoints,0] = session.mediaPipeData[0][ii].left_hand_landmarks.landmark[jj].x#Take x pos of that point
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints+numRightHandPoints,1] = session.mediaPipeData[0][ii].left_hand_landmarks.landmark[jj].y#Take y pos of that point
#                         mediaPipe_nCams_nFrames_nImgPts_XYC[nn,ii,jj+numBodyPoints+numFacePoints+numRightHandPoints,2] = session.mediaPipeData[0][ii].left_hand_landmarks.landmark[jj].visibility#Take visibility(confidence) pos of that point
#             #print(session.mediaPipe_datalist[0].pose_landmarks.landmark[0].x)

#         #path_to_mediapipe_2d = session.dataArrayPath/'mediaPipeData_nCams_nFrames_nImgPts_XY.npy'
        
#         mediaPipeData_nCams_nFrames_nImgPts_XY =  mediaPipe_nCams_nFrames_nImgPts_XYC[:,:,:,0:2].copy()

#         #mediaPipe_nCams_nFrames_nImgPts_XYC[:, :, :, 0] *= 640
#         #mediaPipe_nCams_nFrames_nImgPts_XYC[:, :, :, 1] *= 480
        
#         np.save(session.dataArrayPath / "mediaPipe_2d.npy", mediaPipe_nCams_nFrames_nImgPts_XYC,)

#         return mediaPipe_nCams_nFrames_nImgPts_XYC