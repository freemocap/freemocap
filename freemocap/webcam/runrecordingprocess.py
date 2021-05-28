from freemocap import recordingconfig
from freemocap.webcam import startcamrecording,timesync,videotrim
from pathlib import Path
import time
import pickle
import pandas as pd 
import numpy as np
from tkinter import Tk,Label, Button, Frame, Listbox, Entry


def RunCams(session,camInputs,parameterDictionary,rotationInput):
   
    
   
    #%% Setting up recordings
    beginTime = time.time()
    numCams = len(camInputs) #number of cameras 
    session.numCams = numCams
    numCamRange = range(numCams) #a range for the number of cameras that we have
    videoNames = []
    camIDs = []
    for x in numCamRange: #create names for each of the initial untrimmed videos 
        singleCamID = 'Cam{}'.format(x+1)
        camIDs.append(singleCamID) #creates IDs for each camera based on the number of cameras entered
        singleVidName = 'raw_cam{}.mp4'.format(x+1)
        videoNames.append(singleVidName)    

    #%% Starting the thread recordings for each camera
    threads = []    
    for n in numCamRange: #starts recording video, opens threads for each camera
        camRecordings = startcamrecording.CamRecordingThread(camIDs[n],camInputs[n],videoNames[n],session.rawVidPath,beginTime,parameterDictionary)
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
    dfT = df.transpose()
    csvName = session.sessionID + '.csv' #create our csv filename
    csvPath = session.sessionPath/csvName
    dfT.to_csv(csvPath) #turn dataframe into a CSV
    
    
    frameTable,timeTable,frameRate,resultsTable,plots = timesync.TimeSync(dfT,numCamRange,camIDs) #start the timesync process
    #this message shows you your percentages and asks if you would like to continue or not. shuts down the program if no
    root = Tk()
    proceed = timesync.proceedGUI(root,resultsTable,plots) #create a GUI instance called proceed
    root.mainloop()


    if proceed.proceed == True: #check if the proceed attribute is set to True
        print()
        print('Starting editing')
        #start editing the videos 
        videotrim.VideoTrim(session,videoNames,frameTable,parameterDictionary,rotationInput,numCamRange)
        videotrim.createCalibrationVideos(session,60,parameterDictionary)
        print('all done')
        
    return proceed.proceed

       