from freemocap.webcam import startcamrecording, timesync, videotrim

from pathlib import Path
import time
import pickle
import pandas as pd
import numpy as np
from tkinter import Tk


def RecordCams(session,camInputs,parameterDictionary,rotationInputs):
    """ 
    Determines the number of cameras, assigns them IDs, and then starts a threaded cam recording process. Accesses the pickle file of timestamps
    saved during recording, makes a dataframe from it and saves it to a CSV file. Updates the session class at the end with numCam variable
    """  
    #Create RawVideos folder
    session.rawVidPath.mkdir(exist_ok = True)

    #%% Setting up recordings
    beginTime = time.time()
    numCams = len(camInputs)  # number of cameras
    numCamRange = range(numCams)  # a range for the number of cameras that we have
    vidNames = []
    camIDs = []
    unix_camIDs = []
    for x in numCamRange:  # create names for each of the initial untrimmed videos
        singleCamID = "Cam{}".format(x + 1)
        camIDs.append(
            singleCamID
        )  # creates IDs for each camera based on the number of cameras entered
        
        unix_camID = singleCamID + '_unix_timestamps'
        unix_camIDs.append(unix_camID)

        singleVidName = "raw_cam{}.mp4".format(x + 1)
        vidNames.append(singleVidName)

    #%% Starting the thread recordings for each camera
    threads = []
    for n in numCamRange:  # starts recording video, opens threads for each camera
        camRecordings = startcamrecording.CamRecordingThread(
            session,
            camIDs[n],
            unix_camIDs[n],
            camInputs[n],
            vidNames[n],
            session.rawVidPath,
            beginTime,
            parameterDictionary,
        )
        camRecordings.start()

        threads.append(camRecordings)

    for camRecordings in threads:
        camRecordings.join()  # make sure that one thread ending doesn't immediately end all the others (before they can dump data in a pickle file)

    print("finished recordings")

    timeStampList = []
    unix_timeStampList = []

    for (
        e
    ) in (
        numCamRange
    ):  # open the saved pickle file for each camera, and add the timestamps to the dataList list
        with open(session.rawVidPath/camIDs[e], "rb") as f:
            camTimeList = pickle.load(f)
            timeStampList.append(camTimeList)
        with open(session.rawVidPath/unix_camIDs[e], "rb") as g:
            unix_camTimeList = pickle.load(g)
            unix_timeStampList.append(unix_camTimeList)

    timeDictionary = {}
    unix_timeDictionary = {}

    id_and_time = zip(camIDs, timeStampList)

    for cam, data in id_and_time:
        timeDictionary[cam] = np.array(
            data
        )  # create a dictionary that holds the timestamps for each camera
    df = pd.DataFrame.from_dict(
        timeDictionary, orient="index"
    )  # create a data frame from this dictionary
    timeStampData = df.transpose()
    csvName = session.sessionID + "_timestamps.csv" 
    csvPath = session.rawVidPath / csvName
    timeStampData.to_csv(csvPath)  # turn dataframe into a CSV

    id_and_unix_time = zip(unix_camIDs,unix_timeStampList)
    
    for cam_unix, data_unix in id_and_unix_time:
        unix_timeDictionary[cam_unix] = np.array(data_unix)
    df_unix = pd.DataFrame.from_dict(
    unix_timeDictionary, orient="index"
    )  # create a data frame from this dictionary
    unix_timeStampData = df_unix.transpose()
    unix_csvName = session.sessionID + "_unix_timestamps.csv"
    unix_csvPath = session.rawVidPath / unix_csvName
    unix_timeStampData.to_csv(unix_csvPath)

    session.numCams = numCams
    session.session_settings['recording_parameters'].update({'numCams':session.numCams})
    session.timeStampData = timeStampData
    session.camIDs = camIDs
    session.numCamRange = numCamRange
    session.vidNames = vidNames

def SyncCams(session, timeStampData,numCamRange,vidNames,camIDs):
    """ 
    Runs the time-syncing process. Accesses saved timestamps, runs the time-syncing GUI, and on user-permission, proceeds to create
    synced videos 
    """  
    session.syncedVidPath.mkdir(exist_ok = True)

    #start the timesync process
    frameTable,timeTable,frameRate,resultsTable,plots = timesync.TimeSync(session,timeStampData,numCamRange,camIDs) 
    
    #this message shows you your percentages and asks if you would like to continue or not. shuts down the program if no
    root = Tk()
    proceed = timesync.proceedGUI(
        root, resultsTable, plots
    )  # create a GUI instance called proceed
    root.mainloop()

    if proceed.proceed == True:
        print()
        print('Starting editing')
        videotrim.VideoTrim(session,vidNames,frameTable,session.parameterDictionary,session.rotationInputs,numCamRange)
        session.session_settings['recording_parameters'].update({'numFrames':session.numFrames})
        #videotrim.createCalibrationVideos(session,60,parameterDictionary)
        print('all done')
