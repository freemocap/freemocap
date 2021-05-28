# -*- coding: utf-8 -*-
"""
Created on Mon Nov 30 12:48:14 2020

@author: Rontc
"""

import cv2
import threading
import pickle 
import time
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import Tk,Label, Button, Frame
#import tkMessageBox
from tqdm import tqdm 
import imutils
import sys 
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from omc import recordingconfig
from pathlib import Path

global beginTime


#create a camera object that can be threaded
class CamThread(threading.Thread): 
    def __init__(self,camID,camInput,videoName,rawVidPath,beginTime,parameterDictionary):
        threading.Thread.__init__(self)
        self.camID = camID
        self.camInput = camInput
        self.videoName = videoName
        self.rawVidPath = rawVidPath
        self.beginTime = beginTime
        self.parameterDictionary = parameterDictionary

    def run(self):
        print("Starting " + self.camID)
        self.timeStamps = CamPreview(self.camID, self.camInput, self.videoName,self.rawVidPath,self.beginTime,self.parameterDictionary)
    def getStamps(self):
        return self.timeStamps
#the recording function that each threaded camera object runs
def CamPreview(camID, camInput, videoName,rawVidPath,beginTime,parameterDictionary):
    #the flag is triggered when the user shuts down one webcam to shut down the rest. 
    #normally I'd try to avoid global variables, but in this case it's 
    #necessary, since each webcam runs as it's own object.
    global flag 
    flag = False 
    
    cv2.namedWindow(camID) #name the preview window for the camera its showing
    cam = cv2.VideoCapture(camInput,cv2.CAP_DSHOW) #create the video capture object
    #if not cam.isOpened():
    #         raise RuntimeError('No camera found at input '+ str(camID)) 
    #pulling out all the dictionary paramters 
    exposure = parameterDictionary.get('exposure')
    resWidth = parameterDictionary.get('resWidth')
    resHeight = parameterDictionary.get('resHeight')
    framerate = parameterDictionary.get('framerate')
    codec = parameterDictionary.get('codec')
    
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, resWidth)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, resHeight)
    cam.set(cv2.CAP_PROP_EXPOSURE, exposure)
    fourcc = cv2.VideoWriter_fourcc(*codec)
    #rawPath = filepath/'RawVideos' #creating a RawVideos folder
    #rawPath.mkdir(parents = True, exist_ok = True)
    width = cam.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cam.get(cv2.CAP_PROP_FRAME_HEIGHT)
    print('width:',width, 'height:',height)
    saveRawVidPath = str(rawVidPath/videoName) #create a save path for each video to the RawVideos folders
    out = cv2.VideoWriter(saveRawVidPath,fourcc, framerate, (resWidth,resHeight))
    timeStamps = [] #holds the timestamps 

    if cam.isOpened():
        success, frame = cam.read()
    else:
        success = False

    while success: #while the camera is opened, record the data until the escape button is hit 
        if flag: #when the flag is triggered, stop recording and dump the data
            with open(camID, 'wb') as f:
               pickle.dump(timeStamps, f)
            break
        success, frame = cam.read()
       
        cv2.imshow(camID, frame)
        frame_sized = cv2.resize(frame,(resWidth,resHeight))
        #frame_sized = frame 
        out.write(frame_sized)
        timeStamps.append(time.time()-beginTime) #add each timestamp to the list
    
        key = cv2.waitKey(20)
        if key == 27:  # exit on ESC
            flag = True #set flag to true to shut down all other webcams
            with open(camID, 'wb') as f:
               pickle.dump(timeStamps, f) #dump the data
            break
    cv2.destroyWindow(camID)
    return timeStamps

#this is how we sync our time frames, based on our recorded timestamps
class proceedGUI:
    def __init__(self, master, results, figure):
        self.master = master
        self.results = results
        self.figure = figure
        master.title("Choose File Path")
        
      
        bottom_frame = Frame(self.master, height = 1000)
        bottom_frame.pack(side = tk.LEFT)
        self.label = Label(bottom_frame, text= results.to_string(index = False))
        self.label.pack(side = tk.TOP)
        self.go_button = Button(bottom_frame, text="Proceed", command=self.destroy)
        self.stop_button = Button(bottom_frame, text="Quit", command= self.stop)
   
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.master)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.LEFT, fill="both", expand=1)
        
        self.stop_button.pack(side = tk.RIGHT)
        self.go_button.pack(side = tk.RIGHT)

        

        

    def stop(self):
          self.master.destroy()
          sys.exit("Quitting Program")
    
    def destroy(self):
          self.master.destroy()
    
def TimeSync(df,numCamRange,camNames):    
       
    def CloseNeighb(camera,point): 
            closestPoint = (np.abs(camera - point)).argmin() 
            return closestPoint

    newFrame = df #read our CSV file 
          

    
    #this section auto-finds the start and end points for our master timeline to the nearest second
    masterTimelineBegin = np.ceil(max(newFrame.iloc[0]))  
    lastPoints = []
    for name in camNames:
        cameraLastPoint = newFrame[name][newFrame[name].last_valid_index()] #find the last non-nan value in each camera
        lastPoints.append(cameraLastPoint)
    
    masterTimelineEnd = np.floor(min(lastPoints))  #find where the fastest camera ended, round down, use that as the end point


    #print('end',endList)
    print('intervals:',masterTimelineBegin,masterTimelineEnd)   
    
    
    totalFrameIntvl= [] #list for storing frame rates for each camera
    
      
    n = 0; #counter for going through camera names
    for x in numCamRange:
      currentCam = newFrame[camNames[x]]
      #finds the closest point in each camera to the start and end points of our timeline
      currentCamStart = CloseNeighb(currentCam,masterTimelineBegin) 
      currentCamEnd = CloseNeighb(currentCam,masterTimelineEnd)
      print("using frames:", currentCamStart,"-",currentCamEnd,"for",camNames[n])
      n +=1
      currentCamTimeline = currentCam[currentCamStart:currentCamEnd] #grab the times from start to finish for each camera
      currentCamFrameInterval = np.mean(np.diff(currentCamTimeline)) #calculate the interval between each frame and take the mean 
      totalFrameIntvl.append(currentCamFrameInterval) #add interval to list 
      #print(camNames[x],currentCamStart,currentCamEnd)
    totalAverageIntvl = np.mean(totalFrameIntvl) #find the total average interval across all cameras
    masterTimeline = np.arange(masterTimelineBegin,masterTimelineEnd,totalAverageIntvl) #build a master timeline with the average interval
       
    #now we start the syncing process
    
    frameList = masterTimeline #start a list of frames, with the first row being our master timeline
    timeList = masterTimeline #start a list of timestamps,with the first row being our master timeline
     
    delNum= []; #stores number of deleted frames/camera
    bufNum= []; #stores number of buffered frames/camera
    bufPercentList = []; #stores percentage of deleted frames/camera
    delPercentList = []; #stores percentage of buffered frames/camera
    
    count = 0 #Keeps track of what frame we're on (I think?)
    n = 0; #I don't remember why I did this but I'm sure I'll figure it out later
    
    for y in numCamRange:
        thisCam = newFrame[camNames[y]]
        camTimes = []; #stored times
        camFrames =[]; #stored frames
    
        count += 1
        #--------------Adjust each camera to start at the first point in the master timeline
        beginFrame = CloseNeighb(thisCam,masterTimeline[0])
        timeDif = masterTimeline[0] - thisCam[beginFrame]
        thisCam = thisCam + timeDif
        
        for z in masterTimeline: #for each point in the master timeline
            closestFrame = CloseNeighb(thisCam, z) #find the closest frame in this camera to each point of the master timeline
            camFrames.append(closestFrame) #add that frame to the list
            camTimes.append(thisCam[closestFrame]) #find the time corresponding to this frame
            
        print("starting detection:",camNames[n]) #now to start finding deleted/buffered slides
        frameList = np.column_stack((frameList,camFrames)) #update our framelist with our new frames
        timeList = np.column_stack((timeList,camTimes)) #update our timelist 
        
    
        #start counters for the number of buffered and deleted slides
        bufCount = 0;
        delCount = 0;
      
        for i in range(0,len(camFrames)-1): 
            distanceBetweenFrames = camFrames[i+1] - camFrames[i] #find the distance between adjacent frames
            if distanceBetweenFrames == 1: #these frames are consecutive, do nothing
                None 
            elif distanceBetweenFrames == 0: #we have a buffered slide
                bufCount += 1
                #this section looks at our two timepoints, and finds the which point on the master timeline is closest 
                frame1 = abs(masterTimeline[i]-camTimes[i])
                frame2 = abs(masterTimeline[i+1]-camTimes[i])
                #finds which frame is closest, and sets the other frame as a buffer (indicated by the -1)
                if frame1>frame2:
                 frameList[i,count] = -1
                 timeList[i,count] = -1
                else:
                 frameList[i+1,count] = -1;
                 timeList[i+1,count] = -1;
            elif distanceBetweenFrames > 1: #deletion
               delCount += 1
            else:
                
                print("something else happened")
        #update and calculate our percentages and numbers for buffers/deletions
        delNum.append(round(delCount,1))
        bufNum.append(round(bufCount,1))
        #print(bufCount,len(frameList))
        bufPercent = (bufCount/len(frameList))*100
        delPercent = (delCount/len(frameList))*100
        bufPercentList.append(round(bufPercent,2))
        delPercentList.append(round(delPercent,2))
       
        #print(delNum,bufNum,bufPercentList,delPercentList)
        #print("deleted frames:",delCount)
        #print("buffered frames:",bufCount)
        n +=1
        
    #create our data frame for both times and frames    
    frameTable = pd.DataFrame(frameList)   
    columnNames = ['Master Timeline'] + camNames
    frameTable.columns = columnNames
    timeTable = pd.DataFrame(timeList)
    timeTable.columns = columnNames
    totalFrameRate = [round(1/intvl,1) for intvl in totalFrameIntvl]
    frameRate = 1/totalAverageIntvl #calculates our framerate 
    results = {'Cam':camNames,'#Del':delNum,'%Del':delPercentList,'#Buf':bufNum,'%Buf':bufPercentList,'FPS':totalFrameRate}
    resultTable = pd.DataFrame(results,columns = ['Cam','#Del','%Del','#Buf','%Buf','FPS'])
    
    #============================================== plot data
    differenceFrame = newFrame.diff(axis = 0)
    fpsFrame = differenceFrame.pow(-1)
    fig = Figure(figsize = [10,10])
    fig.patch.set_facecolor('#F0F0F0')
    a = fig.add_subplot(221)
    a.set_xlabel('Frame')
    a.set_ylabel('Time(s)')
    newFrame.plot(ax = a, title = 'Camera timestamps')
    b = fig.add_subplot(222)
    b.set_xlabel('Frame')
    b.set_ylabel('Frame duration (s)')
    differenceFrame.plot(ax = b, marker = '.', linestyle = 'none',title = 'Camera frame duration') 
    c = fig.add_subplot(223)
    c.set_xlabel('Time (s)')
    differenceFrame.plot.hist(ax = c, bins=6,alpha = .5, xlim = [0,.1], title = 'Frame interval distribution (s)')
    d = fig.add_subplot(224)
    d.set_xlabel('Frames per second')
    fpsFrame.plot.hist(ax = d, bins=6,alpha = .5, xlim = [0,40], title = 'Frames per second distribution')
    return frameTable,timeTable,frameRate,resultTable,fig 
#function to trim our videos 


def VideoEdit(rawVidPath,syncedVidPath, vidList,sessionName,ft,parameterDictionary,rotationState,numCamRange):
    camList = list(ft.columns[1:len(vidList)+1]) #grab the camera identifiers from the data frame 
    resWidth = parameterDictionary.get('resWidth')
    resHeight = parameterDictionary.get('resHeight')
    framerate = parameterDictionary.get('framerate')
    trueWidth = resWidth
    trueHeight = resHeight
    codec = parameterDictionary.get('codec')
    for vid,cam,camNum in zip(vidList,camList,numCamRange): #iterate in parallel through camera identifiers and matching videos
        print('Editing '+cam+' from ' +vid)
        #print(cam+'_'+out_path)
        #rawPath = filepath/'RawVideos'
        cap = cv2.VideoCapture(str(rawVidPath/vid)) #initialize OpenCV capture
        frameTable = ft[cam] #grab the frames needed for that camera
        success, image = cap.read() #start reading frames
        fourcc = cv2.VideoWriter_fourcc(*codec)
        saveName = sessionName +'_synced_' + cam + '.mp4' 
        #syncedPath = filepath/'SyncedVideos'
        #syncedPath.mkdir(parents = True, exist_ok = True)
        
        
        saveSyncedVidPath = str(syncedVidPath/saveName) #create an output path for the function
        if rotationState[camNum] == 90 or rotationState[camNum] == 270:
            tempHeight = resHeight
            resHeight = resWidth
            resWidth = tempHeight
            #print(rotationState[camNum], resHeight, resWidth)
   
        out = cv2.VideoWriter(saveSyncedVidPath, fourcc, framerate, (resWidth,resHeight)) #change resolution as needed
        for frame in tqdm(frameTable, leave = True): #start looking through the frames we need
            if frame == -1: #this is a buffer frame
                blankFrame = np.zeros_like(image) #create a blank frame 
                if rotationState[camNum] is not None:
                   blankFrame = imutils.rotate_bound(blankFrame, angle= rotationState[camNum])
                   #image = cv2.rotate(image,rotateCode = rotationState[camNum])
                   image = cv2.resize(image,(resWidth,resHeight))
                out.write(blankFrame) #write that frame to the video
            else:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame) #set the video to the frame that we need
                success, image = cap.read()
                if rotationState[camNum] is not None:
                   image = imutils.rotate_bound(image, angle= rotationState[camNum])
                   #image = cv2.rotate(image,rotateCode = rotationState[camNum])
                   image = cv2.resize(image,(resWidth,resHeight))
                out.write(image)
        resWidth = trueWidth
        resHeight = trueHeight
        cap.release()
        out.release()
        print('Saved '+ saveSyncedVidPath)
        print()
        
       
#function to run all these above functions together
def RunCams(camInputs,config_yaml_path,sessionName,parameterDictionary,rotationInput):
    csvName = sessionName + '.csv' #create our csv filename
    
    config_settings = recordingconfig.load_config_yaml(config_yaml_path)
    rawVidPath = Path(config_settings['Paths']['rawVidPath'])
    syncedVidPath = Path(config_settings['Paths']['syncedVidPath'])
    
    
    beginTime = time.time()
    numCams = len(camInputs) #number of cameras 
    numCamRange = range(numCams) #a range for the number of cameras that we have
    videoNames = []
    camIDs = []
    for x in numCamRange: #create names for each of the initial untrimmed videos 
        singleCamID = 'Cam{}'.format(x+1)
        camIDs.append(singleCamID) #creates IDs for each camera based on the number of cameras entered
        singleVidName = 'raw_cam{}.mp4'.format(x+1)
        videoNames.append(singleVidName)    
    
    threads = []
    
    for n in numCamRange: #starts recording video, opens threads for each camera
        camRecordings = CamThread(camIDs[n],camInputs[n],videoNames[n],rawVidPath,beginTime,parameterDictionary)
        camRecordings.start()
       
        threads.append(camRecordings) 
    
    for camRecordings in threads:
        camRecordings.join() #make sure that one thread ending doesn't immediately end all the others (before they can dump data in a pickle file)
    
    print('finished')
    
    timeStampList = [] 
    
    for e in numCamRange: #open the saved pickle file for each camera, and add the timestamps to the dataList list
      with open(camIDs[e], 'rb') as f:
        camTimeList = pickle.load(f)
        timeStampList.append(camTimeList)
    
    timeDictionary = {}  #our dictionary   
        
    id_and_time = zip(camIDs,timeStampList)  
    
    for cam,data in id_and_time:
        timeDictionary[cam] = np.array(data)  #create a dictionary that holds the timestamps for each camera 
    
        
    df = pd.DataFrame.from_dict(timeDictionary, orient = 'index') #create a data frame from this dictionary
    dfT = df.transpose()
    csvPath = Path(config_settings['Paths']['sessionPath'])/csvName
    dfT.to_csv(csvPath) #turn dataframe into a CSV
    
    
    frameTable,timeTable,frameRate,resultsTable,plots = TimeSync(dfT,numCamRange,camIDs) #start the timesync process
    #this message shows you your percentages and asks if you would like to continue or not. shuts down the program if no
    root = Tk()

    proceed = proceedGUI(root,resultsTable,plots)
    root.mainloop()

    
    print()
    print('Starting editing')
    #start editing the videos 
    VideoEdit(rawVidPath,syncedVidPath,videoNames,sessionName,frameTable,parameterDictionary,rotationInput,numCamRange)
    
    
    print('all done')
    
def TestDevice(source):
   cap = cv2.VideoCapture(source,cv2.CAP_DSHOW) 
   #if cap is None or not cap.isOpened():
       #print('Warning: unable to open video source: ', source)
   
   if cap.isOpened():
        #print('Opened: ',source)
        #print('Exposure: '+ str(cap.get(cv2.CAP_PROP_EXPOSURE)))
        #time.sleep(3)
        cap.release()
        cv2.destroyAllWindows() 
        open_cam = source
        return open_cam
   else:
        return None 

def CheckCams():
    openCamList = []
    for x in tqdm(range(20)):#range 20 right now to be safe
       openCamera = TestDevice(x)
       if openCamera is not None:
          openCamList.append(openCamera)
    
    return openCamList
       
class VideoSetup(threading.Thread):
     def __init__(self, camID,parameterDictionary,rotNum):
         self.camID = camID
         self.parameterDictionary = parameterDictionary
         self.rotNum = rotNum
         threading.Thread.__init__(self)
     def run(self):
        #print("Starting " + self.previewName)
         self.record(self.parameterDictionary,self.rotNum)
     def record(self,parameterDictionary,rotNum):
         exposure = parameterDictionary.get('exposure')
         resWidth = parameterDictionary.get('resWidth')
         resHeight = parameterDictionary.get('resHeight')
         camName = "Camera" + str(self.camID)
         
         cv2.namedWindow(camName)
         cap = cv2.VideoCapture(self.camID,cv2.CAP_DSHOW)
         cap.set(cv2.CAP_PROP_FRAME_WIDTH, resWidth)
         cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resHeight)
         cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
         #print('exposure',cap.get(cv2.CAP_PROP_EXPOSURE))
         #if not cap.isOpened():
          #   raise RuntimeError('No camera found at input '+ str(self.camID)) 
         while True:
             ret1,frame1 = cap.read()
             if ret1 ==True:
                 if rotNum is not None:
                   frame1 = imutils.rotate_bound(frame1, angle= rotNum)
                 cv2.imshow(camName,frame1)
                 if cv2.waitKey(1) & 0xFF== 27:
                     # == ord('q') for q
                    break 
         
             else:
                break
         cv2.destroyWindow(camName)
         

#function to trim our videos 



       
def DebugTime(sessionName,recordPath):    
       
    def CloseNeighb(camera,point): 
            closestPoint = (np.abs(camera - point)).argmin() 
            return closestPoint
    csvName = sessionName + '.csv'
    csvPath = recordPath/csvName
    newFrame = pd.read_csv (csvPath)
    newFrame = newFrame.iloc[:,1:]
    camNames = list(newFrame.columns)
    numCamRange = range(len(camNames)) 
    
 

    
    #this section auto-finds the start and end points for our master timeline to the nearest second
    masterTimelineBegin = np.ceil(max(newFrame.iloc[0]))  
    lastPoints = []
    for name in camNames:
        cameraLastPoint = newFrame[name][newFrame[name].last_valid_index()] #find the last non-nan value in each camera
        lastPoints.append(cameraLastPoint)
    
    masterTimelineEnd = np.floor(min(lastPoints))  #find where the fastest camera ended, round down, use that as the end point


    #print('end',endList)
    print('intervals:',masterTimelineBegin,masterTimelineEnd)   
    
    
    totalFrameIntvl= [] #list for storing frame rates for each camera
    
      
    n = 0; #counter for going through camera names
    for x in numCamRange:
      currentCam = newFrame[camNames[x]]
      #finds the closest point in each camera to the start and end points of our timeline
      currentCamStart = CloseNeighb(currentCam,masterTimelineBegin) 
      currentCamEnd = CloseNeighb(currentCam,masterTimelineEnd)
      print("using frames:", currentCamStart,"-",currentCamEnd,"for",camNames[n])
      print(n)
      n +=1
      currentCamTimeline = currentCam[currentCamStart:currentCamEnd] #grab the times from start to finish for each camera
      currentCamFrameInterval = np.mean(np.diff(currentCamTimeline)) #calculate the interval between each frame and take the mean 
      totalFrameIntvl.append(currentCamFrameInterval) #add interval to list 
      #print(camNames[x],currentCamStart,currentCamEnd)
    
    totalAverageIntvl = np.mean(totalFrameIntvl) #find the total average interval across all cameras
    masterTimeline = np.arange(masterTimelineBegin,masterTimelineEnd,totalAverageIntvl) #build a master timeline with the average interval
       
    #now we start the syncing process
    
    frameList = masterTimeline #start a list of frames, with the first row being our master timeline
    timeList = masterTimeline #start a list of timestamps,with the first row being our master timeline
     
    delNum= []; #stores number of deleted frames/camera
    bufNum= []; #stores number of buffered frames/camera
    bufPercentList = []; #stores percentage of deleted frames/camera
    delPercentList = []; #stores percentage of buffered frames/camera
    
    count = 0 #Keeps track of what frame we're on (I think?)
    n = 0; #I don't remember why I did this but I'm sure I'll figure it out later
    
    for y in numCamRange:
        thisCam = newFrame[camNames[y]]
        camTimes = []; #stored times
        camFrames =[]; #stored frames
    
        count += 1
        #--------------Adjust each camera to start at the first point in the master timeline
        beginFrame = CloseNeighb(thisCam,masterTimeline[0])
        timeDif = masterTimeline[0] - thisCam[beginFrame]
        thisCam = thisCam + timeDif
        
        for z in masterTimeline: #for each point in the master timeline
            closestFrame = CloseNeighb(thisCam, z) #find the closest frame in this camera to each point of the master timeline
            camFrames.append(closestFrame) #add that frame to the list
            camTimes.append(thisCam[closestFrame]) #find the time corresponding to this frame
            
        print("starting detection:",camNames[n]) #now to start finding deleted/buffered slides
        frameList = np.column_stack((frameList,camFrames)) #update our framelist with our new frames
        timeList = np.column_stack((timeList,camTimes)) #update our timelist 
        
    
        #start counters for the number of buffered and deleted slides
        bufCount = 0;
        delCount = 0;
      
        for i in range(0,len(camFrames)-1): 
            distanceBetweenFrames = camFrames[i+1] - camFrames[i] #find the distance between adjacent frames
            if distanceBetweenFrames == 1: #these frames are consecutive, do nothing
                None 
            elif distanceBetweenFrames == 0: #we have a buffered slide
                bufCount += 1
                #this section looks at our two timepoints, and finds the which point on the master timeline is closest 
                frame1 = abs(masterTimeline[i]-camTimes[i])
                frame2 = abs(masterTimeline[i+1]-camTimes[i])
                #finds which frame is closest, and sets the other frame as a buffer (indicated by the -1)
                if frame1>frame2:
                 frameList[i,count] = -1
                 timeList[i,count] = -1
                else:
                 frameList[i+1,count] = -1;
                 timeList[i+1,count] = -1;
            elif distanceBetweenFrames > 1: #deletion
               delCount += 1
            else:
                
                print("something else happened")
        #update and calculate our percentages and numbers for buffers/deletions
        delNum.append(round(delCount,1))
        bufNum.append(round(bufCount,1))
        #print(bufCount,len(frameList))
        bufPercent = (bufCount/len(frameList))*100
        delPercent = (delCount/len(frameList))*100
        bufPercentList.append(round(bufPercent,2))
        delPercentList.append(round(delPercent,2))
       
        #print(delNum,bufNum,bufPercentList,delPercentList)
        #print("deleted frames:",delCount)
        #print("buffered frames:",bufCount)
        n +=1
        
    #create our data frame for both times and frames    
    frameTable = pd.DataFrame(frameList)   
    columnNames = ['Master Timeline'] + camNames
    frameTable.columns = columnNames
    timeTable = pd.DataFrame(timeList)
    timeTable.columns = columnNames
    totalFrameRate = [round(1/intvl,1) for intvl in totalFrameIntvl]
    frameRate = 1/totalAverageIntvl #calculates our framerate 
    results = {'Cam':camNames,'#Del':delNum,'%Del':delPercentList,'#Buf':bufNum,'%Buf':bufPercentList,'FPS':totalFrameRate}
    resultTable = pd.DataFrame(results,columns = ['Cam','#Del','%Del','#Buf','%Buf','FPS'])
    
    #============================================== plot data
    differenceFrame = newFrame.diff(axis = 0)
    fpsFrame = differenceFrame.pow(-1)
    fig = Figure(figsize = [10,10])
    fig.patch.set_facecolor('#F0F0F0')
    a = fig.add_subplot(221)
    a.set_xlabel('Frame')
    a.set_ylabel('Time(s)')
    newFrame.plot(ax = a, title = 'Camera timestamps')
    b = fig.add_subplot(222)
    b.set_xlabel('Frame')
    b.set_ylabel('Frame duration (s)')
    differenceFrame.plot(ax = b, title = 'Camera frame duration') 
    c = fig.add_subplot(223)
    c.set_xlabel('Time (s)')
    differenceFrame.plot.hist(ax = c, bins=6,alpha = .5, xlim = [0,.1], title = 'Frame interval distribution (s)')
    d = fig.add_subplot(224)
    d.set_xlabel('Frames per second')
    fpsFrame.plot.hist(ax = d, bins=6,alpha = .5, xlim = [0,40], title = 'Frames per second distribution')
    root = Tk()

    proceedGUI(root,resultTable,fig)
    root.mainloop()