import numpy as np
import pandas as pd
import sys
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import Tk, Label, Button, Frame

def TimeSync(session,timeStampData,numCamRange,camNames):    
    """
    First creates a master timeline from the average frame length interval across all cameras. Then proceeds to compare timepoints in master timeline
    to timestamps in each camera and find the closest matching timestamp in a camera to a point on the master timeline and create a list of
    frame numbers.

    Then loop through the list of frame numbers from each camera. Update counts for missing frames and duplicated frames. Create a table with these counts
    and plots of statistics related to the recording
    """
    def CloseNeighb(camera,point): 
        """ 
        Find the timestamp in the camera timestamp list that most closely matches the input pointin the master timeline
        """  
        closestPoint = (np.abs(camera - point)).argmin() 
        return closestPoint

    # this section auto-finds the start and end points for our master timeline to the nearest second
    masterTimelineBegin = np.ceil(max(timeStampData.iloc[0]))
    lastPoints = []
    for name in camNames:
        cameraLastPoint = timeStampData[name][
            timeStampData[name].last_valid_index()
        ]  # find the last non-nan value in each camera
        lastPoints.append(cameraLastPoint)
    
    masterTimelineEnd = np.floor(min(lastPoints))  #find where the fastest camera ended, round down, use that as the end point


    #print('end',endList)
    print('intervals:',masterTimelineBegin,masterTimelineEnd)   
    
    preSyncTotalNumFrames = []
    totalFrameIntvl= [] #list for storing frame rates for each camera
    
      
    n = 0; #counter for going through camera names
    for x in numCamRange:
      currentCam = timeStampData[camNames[x]]
      #finds the closest point in each camera to the start and end points of our timeline
      currentCamStart = CloseNeighb(currentCam,masterTimelineBegin) 
      currentCamEnd = CloseNeighb(currentCam,masterTimelineEnd)
    

      print("using frames:", currentCamStart,"-",currentCamEnd,"for",camNames[n])
      n +=1
      currentCamTimeline = currentCam[currentCamStart:currentCamEnd] #grab the times from start to finish for each camera

      currentCamNumFrames = len(currentCamTimeline)

      currentCamFrameInterval = np.mean(np.diff(currentCamTimeline)) #calculate the interval between each frame and take the mean 
      
      totalFrameIntvl.append(currentCamFrameInterval) #add interval to list 
      preSyncTotalNumFrames.append(currentCamNumFrames)
      #print(camNames[x],currentCamStart,currentCamEnd)

    #print(preSyncTotalNumFrames, 'presync')
    #assert preSyncTotalNumFrames.count(preSyncTotalNumFrames[0]) == len(preSyncTotalNumFrames), "Number of frames sliced for each camera pre-syncing is not the same"

    totalAverageIntvl = np.mean(totalFrameIntvl) #find the total average interval across all cameras
    masterTimeline = np.arange(masterTimelineBegin,masterTimelineEnd,totalAverageIntvl) #build a master timeline with the average interval
       
    #now we start the syncing process
    
    frameList = masterTimeline #start a list of frames, with the first row being our master timeline
    timeList = masterTimeline #start a list of timestamps,with the first row being our master timeline
    
    unix_converted_timeList = range(len(masterTimeline)) #keep a record of unix timestamps before they're normalized to fit the master timeline
    delNum= []; #stores number of deleted frames/camera
    bufNum= []; #stores number of buffered frames/camera
    bufPercentList = []; #stores percentage of deleted frames/camera
    delPercentList = []; #stores percentage of buffered frames/camera
    
    count = 0 #Keeps track of what frame we're on (I think?)
    n = 0; #I don't remember why I did this but I'm sure I'll figure it out later
    

    postSyncTotalNumFrames = []
    for y in numCamRange:
        thisCam = timeStampData[camNames[y]]
        camTimes = []
        original_camTimes = []
        # stored times
        camFrames = []
        # stored frames

        count += 1
        # --------------Adjust each camera to start at the first point in the master timeline
        beginFrame = CloseNeighb(thisCam, masterTimeline[0])
        timeDif = masterTimeline[0] - thisCam[beginFrame]
        thisCam = thisCam + timeDif
        
        for z in masterTimeline: #for each point in the master timeline
            closestFrame = CloseNeighb(thisCam, z) #find the closest frame in this camera to each point of the master timeline
            camFrames.append(closestFrame) #add that frame to the list
            camTimes.append(thisCam[closestFrame]) #find the time corresponding to this frame
            
        print("starting detection:",camNames[n]) #now to start finding deleted/buffered slides
        frameList = np.column_stack((frameList,camFrames)) #update our framelist with our new frames
        timeList = np.column_stack((timeList,camTimes)) #update our timelist 
        
        original_camTimes = camTimes - timeDif
        if session.get_synced_unix_timestamps == True: #this is bad coding please forgive me - 
            unix_converted_original_camTimes = original_camTimes + session.beginTime
            unix_converted_timeList = np.column_stack((unix_converted_timeList,unix_converted_original_camTimes))
        else:
            unix_converted_original_camTimes = original_camTimes 
            unix_converted_timeList = np.column_stack((unix_converted_timeList,unix_converted_original_camTimes))

    
        #start counters for the number of buffered and deleted slides
        bufCount = 0
        delCount = 0

        thisCamNumFrames = len(camFrames)
        postSyncTotalNumFrames.append(thisCamNumFrames)

        for i in range(0,len(camFrames)-1): 
            distanceBetweenFrames = camFrames[i+1] - camFrames[i] #find the distance between adjacent frames
            if distanceBetweenFrames == 1: #these frames are consecutive, do nothing
                None 
            elif distanceBetweenFrames == 0: #we have a buffered slide
                bufCount += 1
                # this section looks at our two timepoints, and finds the which point on the master timeline is closest
                frame1 = abs(masterTimeline[i] - camTimes[i])
                frame2 = abs(masterTimeline[i + 1] - camTimes[i])
                # finds which frame is closest, and sets the other frame as a buffer (indicated by the -1)
                if frame1 > frame2:
                    frameList[i, count] = -1
                    timeList[i, count] = -1
                    unix_converted_timeList[i,count] = -1
                else:
                    frameList[i + 1, count] = -1
                    timeList[i + 1, count] = -1
                    unix_converted_timeList[i+1,count] = -1
            elif distanceBetweenFrames > 1:  # deletion
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

    #print(postSyncTotalNumFrames, 'post-sync')
    assert postSyncTotalNumFrames.count(postSyncTotalNumFrames[0]) == len(postSyncTotalNumFrames), "Number of frames sliced for each camera post-syncing is not the same"

    session.postSyncNumFrames = postSyncTotalNumFrames[0]

    #create our data frame for both times and frames    
    frameTable = pd.DataFrame(frameList)   
    columnNames = ['Master Timeline'] + camNames
    frameTable.columns = columnNames
    timeTable = pd.DataFrame(timeList)
    timeTable.columns = columnNames

    unix_synced_timeTable = pd.DataFrame(unix_converted_timeList)
    unix_synced_table_columnNames = ['Frame'] + camNames
    unix_synced_timeTable.columns = unix_synced_table_columnNames

    totalFrameRate = [round(1 / intvl, 1) for intvl in totalFrameIntvl]
    frameRate = 1 / totalAverageIntvl  # calculates our framerate
    results = {
        "Cam": camNames,
        "#Del": delNum,
        "%Del": delPercentList,
        "#Buf": bufNum,
        "%Buf": bufPercentList,
        "FPS": totalFrameRate,
    }
    resultTable = pd.DataFrame(
        results, columns=["Cam", "#Del", "%Del", "#Buf", "%Buf", "FPS"]
    )

    # ============================================== plot data
    differenceFrame = timeStampData.diff(axis=0)
    fpsFrame = differenceFrame.pow(-1)
    fig = Figure(figsize=[10, 10])
    fig.patch.set_facecolor("#F0F0F0")
    a = fig.add_subplot(221)
    a.set_xlabel("Frame")
    a.set_ylabel("Time(s)")
    timeStampData.plot(ax=a, title="Camera timestamps")
    b = fig.add_subplot(222)
    b.set_xlabel("Frame")
    b.set_ylabel("Frame duration (s)")
    differenceFrame.plot(
        ax=b, marker=".", linestyle="none", title="Camera frame duration"
    )
    c = fig.add_subplot(223)
    c.set_xlabel("Time (s)")
    differenceFrame.plot.hist(
        ax=c, bins=6, alpha=0.5, xlim=[0, 0.1], title="Frame interval distribution (s)"
    )
    d = fig.add_subplot(224)
    d.set_xlabel("Frames per second")
    fpsFrame.plot.hist(
        ax=d, bins=6, alpha=0.5, xlim=[0, 40], title="Frames per second distribution"
    )
    return frameTable, timeTable, unix_synced_timeTable,frameRate, resultTable, fig


# function to trim our videos


class proceedGUI:
    """ 
    GUI that displays all statistics from recording, and then asks for user input on whether to proceed with the rest of the pipeline
    """  
    def __init__(self, master, results, figure):
        self.master = master
        self.results = results
        self.figure = figure
        self.proceed = ""
        master.title("Choose File Path")

        bottom_frame = Frame(self.master, height=1000)
        bottom_frame.pack(side=tk.LEFT)
        self.label = Label(bottom_frame, text=results.to_string(index=False))
        self.label.pack(side=tk.TOP)
        self.go_button = Button(bottom_frame, text="Proceed", command=self.destroy)
        self.stop_button = Button(bottom_frame, text="Quit", command=self.stop)

        self.canvas = FigureCanvasTkAgg(self.figure, master=self.master)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.LEFT, fill="both", expand=1)

        self.stop_button.pack(side=tk.RIGHT)
        self.go_button.pack(side=tk.RIGHT)

    def stop(self):
        self.master.destroy()
        sys.exit("Quitting Program")

    def destroy(self):
        self.proceed = True
        self.master.destroy()




def time_sync_initialize(session):
    """
    Initialize settings specific to the time syncing stage if running stage 2
    """
    #from the config settings add the camera input parameters to parameter dictionary
    session.initialize(stage = 2)
    session.parameterDictionary = session.session_settings['recording_parameters']['ParameterDict']
    rotationDict = session.session_settings['recording_parameters']['RotationInputs']
    session.rotationInputs = list(rotationDict.values())
    #initialize the path to the timestamp csv
    csvName = session.sessionID + '_timestamps.csv'
    csvPath = session.rawVidPath/csvName

    #read CSV data, turn it into a data frame
    timeStampData = pd.read_csv (csvPath)
    timeStampData = timeStampData.iloc[:,1:]

    #get the camIDs and number of cameras (numCamRange) from the dataframe
    camIDs = list(timeStampData.columns)
    numCams = len(camIDs)
    numCamRange = range(len(camIDs)) 
    
    #create names for each of the raw videos  
    vidNames = []
    for x in numCamRange:
        singleVidName = 'raw_cam{}.mp4'.format(x+1)
        vidNames.append(singleVidName)    

    if session.get_synced_unix_timestamps == True:
        unix_timestamp_csvName = session.sessionID + "_unix_timestamps.csv"
        unixTimeStampDataPath = session.rawVidPath/unix_timestamp_csvName
        cam_to_search_for_begin_time = camIDs[0] + '_unix_timestamps'
        unix_timestamp_data = pd.read_csv(unixTimeStampDataPath)
        unix_timestamp_data = unix_timestamp_data.iloc[:,1:]
        beginTime = unix_timestamp_data[cam_to_search_for_begin_time][0]
        session.beginTime = beginTime
    #initialize all the session variables we'll need to run the rest of the pipeline
    session.timeStampData = timeStampData
    session.camIDs = camIDs
    session.numCamRange = numCamRange
    session.vidNames = vidNames
    session.numCams = numCams
  
