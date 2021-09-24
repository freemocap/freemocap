from freemocap import fmc_runme,recordingconfig

import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import Tk, Label, Button, Frame, Listbox, Entry, filedialog
import requests
import io

def DemoSetup():

    
    download_data = runDataDownloadGUI() #ask for user input on downloading
    
    zip_file_url = "https://ndownloader.figshare.com/files/28927743"
    sample_session_name = 'sesh_21-07-20_165209'
    sample_session_zip = sample_session_name + '.zip'

    if  download_data: #if they want to download
        #code to download stuff from online will go here
        destinationPath = runDemoGUI() 
     
        #error seems to expect the sample session to still be a zip file even though it is unzipped below

        
        if 'FreeMocap_Data' in str(destinationPath):
            print('using a freemocap data folder')
            #extractToPath = destinationPath/sample_session_zip
            extractToPath = destinationPath
        else:
            extractToFolder = Path(destinationPath)/recordingconfig.dataFolder #append the name of the data folder to the destination path
            extractToFolder.mkdir(exist_ok=True) #make the data folder if it doesn't current exist
            #extractToPath = extractToFolder/sample_session_name
            extractToPath = extractToFolder

        #run the GUI to get the directory locations of the zipped folder, and where to extract it to
        #locationPath, destinationPath = runDemoGUI() 
        #zipPath = Path(locationPath)/'sesh_21-07-18_170130.zip' #append the name of the zipped sample file to the path to find it
 

        print('Starting demo session download')
        r = requests.get(zip_file_url)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(extractToPath)

        print('Demo session downloaded to: ' + str(destinationPath) + '/' + str(sample_session_zip))
        #with zipfile.ZipFile(zipPath,'r') as zip_ref:
        #    zip_ref.extractall(extractToPath) #extract stuff to the data folder
    else:
        root = tk.Tk() #bring up a window to select the data folder directory
        root.withdraw()
        destinationPath = filedialog.askdirectory( title='Select the directory where the Freemocap_data folder with the sample data is located',
            initialdir= Path.cwd())


    return extractToPath, sample_session_name #take the path to the directory where the data folder is located

class DemoGUI(): #GUI to pick the location and the destination directories for the sample data 
        def __init__(self, master):
            self.master = master
            
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
    destinationPath = pathchoices.destinationPath

    return destinationPath

def runDataDownloadGUI():
    root = tk.Tk()
    download_options = dataDownloadGUI(root)
    root.mainloop()

    return download_options.download_sample_data


