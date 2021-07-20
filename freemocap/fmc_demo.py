from freemocap import fmc_runme,recordingconfig

import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import Tk, Label, Button, Frame, Listbox, Entry, filedialog

def DemoSetup():

    
    download_data = runDataDownloadGUI() #ask for user input on downloading
    
    if  download_data: #if they want to download
        #code to download stuff from online will go here


        #run the GUI to get the directory locations of the zipped folder, and where to extract it to
        locationPath, destinationPath = runDemoGUI() 
        zipPath = Path(locationPath)/'sesh_21-07-18_170130.zip' #append the name of the zipped sample file to the path to find it
        extractToPath = Path(destinationPath)/recordingconfig.dataFolder #append the name of the data folder to the destination path
        extractToPath.mkdir(exist_ok=True) #make the data folder if it doesn't current exist
        
        with zipfile.ZipFile(zipPath,'r') as zip_ref:
            zip_ref.extractall(extractToPath) #extract stuff to the data folder
    else:
        root = tk.Tk() #brinng up a window to select the data folder directory
        root.withdraw()
        destinationPath = filedialog.askdirectory( title='Select the directory where the Freemocap_data folder with the sample data is located',
            initialdir= Path.cwd())


    return destinationPath #take the path to the directory where the data folder is located

class DemoGUI(): #GUI to pick the location and the destination directories for the sample data 
        def __init__(self, master):
            self.master = master
            
            dataText = "Select the directory where your sample data is located"
            dataLable = Label(master, text=dataText)
            dataLable.pack(side="top")

            self.locationPathVar = tk.StringVar()
            savedLocationLabel = Label(master,textvariable=self.locationPathVar)
            savedLocationLabel.pack()

            dataButton = Button(master,text = 'Select the current sample data location',command = self.openLocationDialog)
            dataButton.pack()

            sampleDestinationText = "If a {} folder already exists, choose the directory where it is located. \n Otherwise, choose a directory to create a {} folder".format(recordingconfig.dataFolder,recordingconfig.dataFolder)
            sampleDestinationLabel = Label(master, text=sampleDestinationText)
            sampleDestinationLabel.pack()

            self.destinationPathVar = tk.StringVar()
            savedDestinationLabel = Label(master,textvariable=self.destinationPathVar)
            savedDestinationLabel.pack()

            sampleDestinationButton = Button(master,text = 'Select the sample data destination',command = self.openDestinationDialog)
            sampleDestinationButton.pack()

            submitButton = Button(master,text = 'Submit',command = self.submit)
            submitButton.pack()

        def openLocationDialog(self):
     
            self.locationPath = filedialog.askdirectory(
            title='Select the directory where the sample data zip file is located',
            initialdir= Path.cwd())

            self.locationPathVar.set(self.locationPath)
            f = 2
        
        def openDestinationDialog(self):
     
            self.destinationPath = filedialog.askdirectory(
            title='Select the directory where the freemocap data is located or should be created',
            initialdir= Path.cwd())
            f = 2

            self.destinationPathVar.set(self.destinationPath)
        
        def submit(self):
            self.master.destroy()


        def getLocationPath(self):
            return self.locationPath
        
        def getDestinationPath(self):
            return self.destinationPath

class dataDownloadGUI(): #GUI to ask whether users want to download data
    def __init__(self, master):
        self.master = master
    
        dataText = "Would you like to download sample data?"
        dataLable = Label(master, text=dataText)
        dataLable.pack(side="top")

        yesButton =  Button(master,text = 'Yes',command = self.yes)
        yesButton.pack()

        noButton =  Button(master,text = 'No',command = self.no)
        noButton.pack()

    def yes(self):
        self.download_sample_data = True
        self.master.destroy()
        

    def no(self):
        self.download_sample_data = False
        self.master.destroy()


def runDemoGUI():
    root = tk.Tk()
    pathchoices = DemoGUI(root)
    root.mainloop()

    locationPath = pathchoices.locationPath
    destinationPath = pathchoices.destinationPath

    return locationPath,destinationPath

def runDataDownloadGUI():
    root = tk.Tk()
    download_options = dataDownloadGUI(root)
    root.mainloop()

    return download_options.download_sample_data


