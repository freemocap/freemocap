# -*- coding: utf-8 -*-
"""
Created on Wed Mar  3 12:18:46 2021

@author: Rontc
"""
import tkinter as tk
from tkinter import Tk, Label, Button, Frame, Listbox, Entry, filedialog
from freemocap.webcam import checkcams
import pickle
import datetime
from pathlib import Path
import sys


class recordGUI:
    # this GUI detects how many cameras you have available and presents them in
    # a listbox, and allows you to pick a task for the cameras
    def __init__(self, master):
        self.master = master
        self.refresh = False 
        # Detect how many inputs you have available
        available_inputs = checkcams.CreateAvailableCamList()
        number_of_cams = len(available_inputs)
        cam_statement = (
            "You have "
            + str(number_of_cams)
            + " cameras available at inputs "
            + str(available_inputs)
        )

        self.master.title("Choose Your Cameras/Task")
        bottom_frame = Frame(self.master, height=100)
        bottom_frame.pack(side=tk.BOTTOM)
        # ---creates a listbox with all the available camera choices
        self.list_box = Listbox(self.master, selectmode="multiple")
        for i in available_inputs:
            self.list_box.insert(i, str(i))

        # ---setting up the task radiobutton
        # creates the different options and the values associated with them
        options = [("Setup", "setup"), ("Record", "record")]

        # initializes currentTask as a string variable and defaults it to setup
        self.currentTask = tk.StringVar()
        self.currentTask.set("setup")

        # ---display the detection results
        tk.Label(self.master, text=cam_statement, justify=tk.RIGHT).pack()
        tk.Label(self.master, text="Select Your Cameras", justify=tk.RIGHT).pack()
        self.list_box.pack()

        # ---create the task radiobutton
        tk.Label(
            self.master, text="""Choose your task""", justify=tk.LEFT, padx=20
        ).pack()

        for option, val in options:
            tk.Radiobutton(
                self.master, text=option, padx=20, variable=self.currentTask, value=val
            ).pack(anchor=tk.W)

        self.refresh_button = Button(bottom_frame, text="Refresh", command=self.Refresh)
        self.refresh_button.pack(side=tk.RIGHT)

        
        self.sub_button = Button(bottom_frame, text="Submit", command=self.Submit)
        self.sub_button.pack(side=tk.RIGHT)

        
    def Submit(self):
        self.taskChoice = self.currentTask.get()
        self.selected = [
            int(self.list_box.get(pos)) for pos in self.list_box.curselection()
        ]
        self.refresh = False
        self.master.destroy()
    
    def Refresh(self):
        self.refresh = True
        self.master.destroy()



class SettingsGUI:
    def __init__(
        self,
        master,
        cam_inputs,
        parameter_dictionary,
        rotation_dictionary,
        sessionID_in,
        task,
        current_path_to_save,
    ):
        self.master = master
        self.cam_inputs = cam_inputs
        self.parameter_dictionary = parameter_dictionary
        self.rotation_dictionary = rotation_dictionary
        self.sessionID_in = sessionID_in
        self.task = task
        self.currentPath = current_path_to_save
        self.mediaPipeOverlay = False
        # check if any previous parameters exist
        if self.parameter_dictionary is not None:
            existing_parameters = True
        else:
            existing_parameters = False

        # check to see if there are any stored rotations for the cameras chosen
        rotationValues = self.RotationRetrieval(cam_inputs, rotation_dictionary)

        # create frames to organize rotation inputs, resolution inputs, and parameter inputs
        topFrame = Frame(self.master)
        topFrame.pack(side=tk.TOP)
        if self.task == 'record':
            recordingSettingsFrame = Frame(self.master)
            recordingSettingsFrame.pack()
        rotLabelFrame = Frame(self.master)
        rotLabelFrame.pack()
        resFrame = Frame(self.master)
        resFrame.pack()
        parametersFrame = Frame(self.master)
        parametersFrame.pack()
        bottomFrame = Frame(self.master).pack(side=tk.BOTTOM)

      

        taskText = "Current Task: " + self.task
        taskLabel = Label(topFrame, text=taskText, font="bold")
        taskLabel.pack()
        # ---Rotation Options. Dynamically creates radio button options depending
        # ---on how many cameras there are
        rotation_options = [
            ("rotate 0", 0),
            ("rotate 90", 90),
            ("rotate 180", 180),
            ("rotate 270", 270),
        ]
        # radVar = tk.IntVar() #Radio Button Variable
        self.rotation_list = []
        rotationRadioButton = {}
        # creates radio buttons for each cam and stores the chosen rotation degree in a list
        for cam, rotDegree in zip(self.cam_inputs, rotationValues):
            current_rotation = tk.IntVar()
            current_rotation.set(rotDegree)
            self.rotation_list.append(current_rotation)
            tk.Label(rotLabelFrame, text="Choose rotation for Cam " + str(cam)).pack()
            for option, degree in rotation_options:
                rotationRadioButton[cam] = tk.Radiobutton(
                    rotLabelFrame, text=option, value=degree, variable=current_rotation
                ).pack()

        # ---Resolution Height and Resolution Width entry
        widthLabel = Label(resFrame, text="Resolution Width").pack(side="left")
        self.resWidthEntry = Entry(resFrame)
        self.resWidthEntry.pack(side="left")
        heightLabel = Label(resFrame, text="Resolution Height").pack(side="left")
        self.resHeightEntry = Entry(resFrame)
        self.resHeightEntry.pack(side="left")

        # ---Exposure,FPS, and codec entry
        exposureLabel = Label(parametersFrame, text="Exposure").pack(side="left")
        self.exposureEntry = Entry(parametersFrame)
        self.exposureEntry.pack(side="left")
        FPSLabel = Label(parametersFrame, text="FPS").pack(side="left")
        self.FPSEntry = Entry(parametersFrame)
        self.FPSEntry.pack(side="left")
        codecLabel = Label(parametersFrame, text="codec").pack(side="left")
        self.codecEntry = Entry(parametersFrame)
        self.codecEntry.pack(side="left")
        
        self.var1 = tk.IntVar()
        c1 = tk.Checkbutton(parametersFrame, text='Mediapipe Overlay',variable=self.var1, onvalue=1, offvalue=0)
        c1.pack(side = 'right')

        # ---SessionID entry- default is the date/time
        if self.task == "record":
            sessionText = "Change SessionID if desired"
            sessionLabel = Label(recordingSettingsFrame, text=sessionText)
            sessionLabel.pack()

            self.sessionIDEntry = Entry(recordingSettingsFrame)
            self.sessionIDEntry.pack()
            self.sessionIDEntry.insert(0, self.sessionID_in)

            pathText = 'Choose where to create your Freemocap_Data folder:'
            pathLabel = Label(recordingSettingsFrame, text=pathText)
            pathLabel.pack()

            text = 'Current file path: ' + self.currentPath
            self.currentPathText = tk.StringVar()
            self.currentPathText.set(text)
            currentPathLabel = Label(recordingSettingsFrame,textvariable = self.currentPathText)
            currentPathLabel.pack()

            self.path_changed = False #will be set to True if the user changes the path with the file dialog

            changepath_button = Button(recordingSettingsFrame,text = 'Change File Path',command = self.openFileDialog)
            changepath_button.pack(side = 'left')
            
            #savedefault_button = Button(recordingSettingsFrame,text = 'Save as Default Path')
            #savedefault_button.pack(side = 'left')
            
        # ---If previous parameters were recieved, insert them into the entry boxes
        if existing_parameters == True:

            self.exposureEntry.insert(0, parameter_dictionary["exposure"])
            self.resWidthEntry.insert(0, parameter_dictionary["resWidth"])
            self.resHeightEntry.insert(0, parameter_dictionary["resHeight"])
            self.codecEntry.insert(0, parameter_dictionary["codec"])
            self.FPSEntry.insert(0, parameter_dictionary["framerate"])

        # ---Submit button to hit when things are finalized
        self.sub_button = Button(bottomFrame, text="Submit", command=self.Submit)
        self.sub_button.pack(side=tk.BOTTOM)

    def openFileDialog(self):
        self.currentPath = filedialog.askdirectory(
        title='Open a file',
        initialdir= Path.cwd())
        self.currentPathText.set('Current file path: ' + self.currentPath)
     

    def Submit(self):
        # get the final entries for all parameters
        # get the rotations for each camera and save them as values of a dictionary
        self.rotation_output = {}
        for count, cam in enumerate(self.cam_inputs):
            self.rotation_output[cam] = self.rotation_list[count].get()

        # built a parameter dictionary by .get()-ing the values from each entry
        self.paramDict = {
            "exposure": int(self.exposureEntry.get()),
            "resWidth": int(self.resWidthEntry.get()),
            "resHeight": int(self.resHeightEntry.get()),
            "framerate": int(self.FPSEntry.get()),
            "codec": str(self.codecEntry.get()),
        }

        if self.var1.get()==1:
            self.mediaPipeOverlay=True

        # spit out the sessionID
        if self.task == "record":
            self.sessionID_out = self.sessionIDEntry.get()
            self.save_path = self.currentPath
        self.master.destroy()

    def RotationRetrieval(self, cam_inputs, rotation_dictionary):
        # takes the input cameras and compares them to the dictionary of
        # rotation values from the last session. For any matching cameras,
        # grab the rotation values. Otherwise, the rotation value is None
        rotationValues = []
        for cam in cam_inputs:
            if cam in rotation_dictionary.keys():
                rotationValues.append(rotation_dictionary[cam])
            else:
                rotationValues.append(0)
        return rotationValues
        
  
        



class ProceedToRecordGUI:
    def __init__(self, master, sessionID_in, current_path_to_save):
        self.master = master
        self.restart_setup = False
        self.sessionID_in = sessionID_in
        self.continueToRecording = ""
        self.sessionID_out = ""
        self.currentPath = current_path_to_save

        sessionText = "Proceed to recording with this sessionID?"
        sessionLabel = Label(master, text=sessionText)
        sessionLabel.pack(side="top")

        self.sessionIDEntry = Entry(master)
        self.sessionIDEntry.pack()
        self.sessionIDEntry.insert(0, self.sessionID_in)


        pathText = 'Choose where to create your data folder:'
        pathLabel = Label(master,text=pathText)
        pathLabel.pack()

        text = 'Current file path: ' + self.currentPath
        self.currentPathText = tk.StringVar()
        self.currentPathText.set(text)
        currentPathLabel = Label(master,textvariable = self.currentPathText)
        currentPathLabel.pack()

        changepath_button = Button(master,text = 'Change Folder Path',command = self.openFileDialog)
        changepath_button.pack(side = 'left')

            # master.title("Proceed to Recording?")
        self.proceed_button = Button(text="Proceed", command=self.proceed)
        self.change_button = Button(text = "Change Parameters", command = self.change_params)
        self.stop_button = Button(text="Quit", command=self.stop)
        self.stop_button.pack(side=tk.RIGHT)
        self.change_button.pack(side = tk.LEFT)
        self.proceed_button.pack(side=tk.RIGHT)


    def openFileDialog(self):
        self.currentPath = filedialog.askdirectory(
        title='Open a file',
        initialdir= Path.cwd())
        self.currentPathText.set('Current file path: ' + self.currentPath)
        

    def stop(self):
        self.master.destroy()
        sys.exit("Quitting Program")

    def change_params(self):
        self.restart_setup = True
        self.sessionID_out = self.sessionIDEntry.get()
        self.save_path = self.currentPath
        self.master.destroy()


    def proceed(self):
        self.continueToRecording = True
        self.sessionID_out = self.sessionIDEntry.get()
        self.save_path = self.currentPath
        self.master.destroy()



def RunChoiceGUI():

    # ---Get the camera inputs and the task
    refresh = True
    while refresh:            
        root = tk.Tk()
        camera_choice = recordGUI(root)
        root.mainloop()
        refresh = camera_choice.refresh

    cam_inputs = camera_choice.selected
    if not cam_inputs:
        raise ValueError("No camera inputs selected")
    task = camera_choice.taskChoice

    return cam_inputs,task


def RunParametersGUI(sessionID_in, rotation_entry, parameter_entry,current_path_to_save,cam_inputs,task):
    # ---Get all the necessary parameters
    root = tk.Tk()
    recording_settings = SettingsGUI(
        root, cam_inputs, parameter_entry, rotation_entry, sessionID_in, task, current_path_to_save
    )
    root.mainloop()

    # ---Create the parameters we'll need to run the records
    # rotation_input = list(test.rotation_output.values())

    paramDict = recording_settings.paramDict

    if task == "record":
        sessionID = recording_settings.sessionID_out
        savepath = recording_settings.save_path
    else:
        sessionID = None
        savepath = None

    return recording_settings.rotation_output, paramDict, sessionID,savepath, recording_settings.mediaPipeOverlay


def RunProceedtoRecordGUI(sessionID_in,current_path_to_save):
    root = tk.Tk()
    goToRecording = ProceedToRecordGUI(root, sessionID_in,current_path_to_save)
    root.mainloop()

    return goToRecording.continueToRecording, goToRecording.restart_setup,goToRecording.sessionID_out, goToRecording.save_path
