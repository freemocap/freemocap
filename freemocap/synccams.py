from freemocap.webcam import timesync
from tkinter import Tk


def RunSync(session, timeStampData,numCamRange,camIDs):
    frameTable,timeTable,frameRate,resultsTable,plots = timesync.TimeSync(timeStampData,numCamRange,camIDs) #start the timesync process
    #this message shows you your percentages and asks if you would like to continue or not. shuts down the program if no
    root = Tk()
    proceed = timesync.proceedGUI(root,resultsTable,plots) #create a GUI instance called proceed
    root.mainloop()
    