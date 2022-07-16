import os
import subprocess
import json

import numpy as np
from rich.progress import track
from ruamel.yaml import YAML
from pathlib import Path

# from numba import jit


def runOpenPose(session, runOpenPose=False):
    """
    Run OpenPose on synced videos, and save bdoy tracking data to be parsed
    """
    if runOpenPose:
        os.chdir(session.openPoseExePath)

    openPose_jsonPathList = []  # list to hold the paths to the json files
    openPose_imgPathList = []
    openPose_imgPathList_yaml = []
    openPose_jsonPathList_yaml = []

    for (
        thisVidPath
    ) in (
        session.syncedVidPath.iterdir()
    ):  # Run OpenPose ('Windows Portable Demo') on each video in the raw video folder
        if (
            thisVidPath.suffix == ".mp4" or thisVidPath.suffix == ".MP4"
        ):  # NOTE - build some list of 'synced video names' and check against that
            print("OpenPosing: ", thisVidPath.name)
            vidPath = session.openPoseDataPath / thisVidPath.stem
            jsonPath = vidPath / "json"
            jsonPath.mkdir(
                parents=True, exist_ok=True
            )  # this camera's json files (with keypoints)
            imgPath = vidPath / "img"
            imgPath.mkdir(parents=True, exist_ok=True)
            openPose_jsonPathList.append(jsonPath)
            openPose_imgPathList.append(imgPath)
            openPose_imgPathList_yaml.append(str(imgPath))
            openPose_jsonPathList_yaml.append(str(jsonPath))
            if runOpenPose:
                subprocess.run(
                    [
                        "bin\OpenPoseDemo.exe",
                        "--video",
                        str(thisVidPath),
                        "--write_json",
                        str(jsonPath),
                        "--net_resolution",
                        "-1x320",
                        "--hand",
                        "--face",
                        "--number_people_max",
                        "1",
                    ],
                    shell=True,
                )
        else:
            print("Skipping: ", thisVidPath.name)
    session.openPose_jsonPathList = openPose_jsonPathList
    session.openPose_imgPathList = openPose_imgPathList
    
    session.session_settings['openPose_imgPathList'] = openPose_imgPathList_yaml
    session.session_settings['openPose_jsonPathList'] = openPose_jsonPathList_yaml
    # yaml = YAML()
    # data = yaml.load(session.session_yaml_path)
    # data['openPose_imgPathList'] = openPose_imgPathList_yaml
    # data['openPose_jsonPathList'] = openPose_jsonPathList_yaml
    # yaml.dump(data, session.session_yaml_path)
    
    os.chdir(session.sessionPath)


# @jit(nopython=True)
def parseOpenPose(session):
    """
    Parse through saved OpenPose data and create a 2D numpy array of tracked body points
    """
    thisCamNum = -1

    ## %%
    #build header for dataframe - NOTE - #openpose data comes in a line ordered 'pixel x location (px)', 'pixel y (py)', 'confidence (conf)' for each keypoint  
    
    dataFrameHeader = []
    bodyCols = 75
    handCols = 63 #per hand
    faceCols = 210 #das alotta face!
    headerLength = bodyCols + 2*handCols + faceCols#should be 411 for whatever version of openpose i was using on 11 Jan 2021
    numImgPoints = headerLength

    for bb in range(0,int(bodyCols/3)): #loop through the number of body markers (i.e. #bodyCols/3)
        dataFrameHeader.append('body_' + str(bb).zfill(3) + '_pixx')
        dataFrameHeader.append('body_' + str(bb).zfill(3) + '_pixy')
        dataFrameHeader.append('body_' + str(bb).zfill(3) + '_conf')

    for hr in range(0,int(handCols/3)): #loop through the number of handR markers (i.e. #handCols/3)
        dataFrameHeader.append('handR_' + str(hr).zfill(3) + '_pixx')
        dataFrameHeader.append('handR_' + str(hr).zfill(3) + '_pixy')
        dataFrameHeader.append('handR_' + str(hr).zfill(3) + '_conf')

    for hl in range(0,int(handCols/3)): #loop through the number of handL markers (i.e. #handCols/3)
        dataFrameHeader.append('handL_' + str(hl).zfill(3) + '_pixx')
        dataFrameHeader.append('handL_' + str(hl).zfill(3) + '_pixy')
        dataFrameHeader.append('handL_' + str(hl).zfill(3) + '_conf')

    for ff in range(0,int(faceCols/3)): #loop through the number of Face markers (i.e. #faceCols/3)
        dataFrameHeader.append('face_' + str(ff).zfill(3) + '_pixx')
        dataFrameHeader.append('face_' + str(ff).zfill(3) + '_pixy')
        dataFrameHeader.append('face_' + str(ff).zfill(3) + '_conf')

    assert len(dataFrameHeader) == headerLength, ['Header is the wrong length! Should be ' +  str(headerLength) + ' but it is ' + str(len(dataFrameHeader)) + ' Check version of OpenPose?']

    ## %% 
    ## load in data from json files
    #numFrames = int(len(list(Path(session.openPose_jsonPathList[0]).glob('*')))) #lol
    numFrames = int(session.numFrames)
    numMarkers= int(int(len(dataFrameHeader)/3))
    numCams = int(session.numCams) #rebuilding numCams here instead of using session.numCams in case 

    openPoseData_nCams_nFrames_nImgPts_XYC = np.ndarray([numCams,numFrames,numMarkers,3]) #hardcoding for now because I am a bad person

    for thisCams_JsonFolderPath in track(session.openPose_jsonPathList, description='Parsing json\'s intow a dataframe (per cam)' ):
        thisCamNum += 1
        # print('Parsing into a dataframe: ', thisCams_JsonFolderPath.name )
        jsonPaths = sorted(Path(thisCams_JsonFolderPath).glob('*.json')) #glob is a "generator(?)" for paths to all the jason for THIS camara            
        
        for thisJsonPath in jsonPaths: #loop throug all the json files and save their 'people' data to a dictionary (which will then be formatted into a pandas dataframe). NOTE - will be empty array if no hoomans visible in frame
            # print('loading: ', thisJsonPath.name)
            frameNum = int(thisJsonPath.stem.split('_')[-2]) #frame number we're on
            thisJsonData = json.loads(thisJsonPath.read_bytes())
            thisJsonData = thisJsonData['people'] # #FEATURE_REQUEST -  at some point, we should check the openpose version (save it with the data somehow, verify everything is the same version, use different markernamlists for different versions, etc)

            if thisJsonData: #if this json has data
                bodyData  = np.array(thisJsonData[0]['pose_keypoints_2d'])
                handRData = np.array(thisJsonData[0]['hand_right_keypoints_2d'])
                handLData = np.array(thisJsonData[0]['hand_left_keypoints_2d'])
                faceData  = np.array(thisJsonData[0]['face_keypoints_2d'])
                thisFrameRow = np.hstack((bodyData,handRData, handLData, faceData)) #horizontally concatenate these arrays      
                f=2          
            else: #if this json is empty, just stuff it fulla NaNs
                thisFrameRow = np.empty([headerLength])
                thisFrameRow.fill(np.nan)


            assert thisFrameRow.size == headerLength, ['Header is the wrong length! Should be ' +  str(headerLength) + ' but it is ' + str(thisFrameRow.size) + ' Check version of OpenPose?']
            
            if frameNum < openPoseData_nCams_nFrames_nImgPts_XYC.shape[1]: #NOTE: THIS SHOULDN"T BE NECESSARY. CURRENT Vid Trim Methods can (apparently) produce vids with off-by-one numbers of frames
                openPoseData_nCams_nFrames_nImgPts_XYC[thisCamNum, frameNum, :, :] = np.reshape(thisFrameRow, [137,3]) #hard coding the number of OpenPose Image Points b/c I'm a bad person
            
        
    

    # session.dataFrameHeader = dataFrameHeader
    # session.numImgPoints = numImgPoints
    #session.numFrames = frameNum  #NOTE - Need to find a safer way to get this number

    path_to_openpose_2d = session.dataArrayPath/'openPoseData_2d.npy'
    np.save(path_to_openpose_2d, openPoseData_nCams_nFrames_nImgPts_XYC)

    return openPoseData_nCams_nFrames_nImgPts_XYC
