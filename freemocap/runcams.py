
from freemocap.webcam import startcamrecording, timesync, videotrim
    
from pathlib import Path
import time
import pickle
import pandas as pd 
import numpy as np
from tkinter import Tk


def RecordCams(session,camInputs,parameterDictionary,rotationInputs):
    #Create RawVideos folder
    session.rawVidPath.mkdir(exist_ok = True)

    #%% Setting up recordings
    beginTime = time.time()
    numCams = len(camInputs) #number of cameras 
    numCamRange = range(numCams) #a range for the number of cameras that we have
    vidNames = []
    camIDs = []
    for x in numCamRange: #create names for each of the initial untrimmed videos 
        singleCamID = 'Cam{}'.format(x+1)
        camIDs.append(singleCamID) #creates IDs for each camera based on the number of cameras entered
        singleVidName = 'raw_cam{}.mp4'.format(x+1)
        vidNames.append(singleVidName)    

    #%% Starting the thread recordings for each camera
    threads = []    
    for n in numCamRange: #starts recording video, opens threads for each camera
        camRecordings = startcamrecording.CamRecordingThread(camIDs[n],camInputs[n],vidNames[n],session.rawVidPath,beginTime,parameterDictionary)
        camRecordings.start()
    
        threads.append(camRecordings) 
    
    for camRecordings in threads:
        camRecordings.join() #make sure that one thread ending doesn't immediately end all the others (before they can dump data in a pickle file)
    
    print('finished recordings')
    
    timeStampList = [] 
    
    for e in numCamRange: #open the saved pickle file for each camera, and add the timestamps to the dataList list
        with open(camIDs[e], 'rb') as f:
            camTimeList = pickle.load(f)
            timeStampList.append(camTimeList)
        
        timeDictionary = {}  
        
    id_and_time = zip(camIDs,timeStampList)  
    
    for cam,data in id_and_time:
        timeDictionary[cam] = np.array(data)  #create a dictionary that holds the timestamps for each camera 
    
        
    df = pd.DataFrame.from_dict(timeDictionary, orient = 'index') #create a data frame from this dictionary
    timeStampData = df.transpose()
    csvName = session.sessionID + '.csv' #create our csv filename
    csvPath = session.sessionPath/csvName
    timeStampData.to_csv(csvPath) #turn dataframe into a CSV

    session.numCams = numCams
    session.session_settings['recording_parameters'].update({'numCams':session.numCams})
    session.timeStampData = timeStampData
    session.camIDs = camIDs
    session.numCamRange = numCamRange
    session.vidNames = vidNames

def SyncCams(session, timeStampData,numCamRange,vidNames,camIDs):
    session.syncedVidPath.mkdir(exist_ok = True)

    #start the timesync process
    frameTable,timeTable,frameRate,resultsTable,plots = timesync.TimeSync(session,timeStampData,numCamRange,camIDs) 
    
    #this message shows you your percentages and asks if you would like to continue or not. shuts down the program if no
    root = Tk()
    proceed = timesync.proceedGUI(root,resultsTable,plots) #create a GUI instance called proceed
    root.mainloop()

    if proceed.proceed == True: 
        print()
        print('Starting editing')
        videotrim.VideoTrim(session,vidNames,frameTable,session.parameterDictionary,session.rotationInputs,numCamRange)
        session.session_settings['recording_parameters'].update({'numFrames':session.numFrames})
        #videotrim.createCalibrationVideos(session,60,parameterDictionary)
        print('all done')