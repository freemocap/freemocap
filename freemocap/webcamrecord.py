# -*- coding: utf-8 -*-
"""
Created on Mon Dec  7 14:16:45 2020

@author: Rontc
"""


from freemocap import recordingconfig 
from freemocap.webcam import recordGUI,camsetup,runrecordingprocess

import tkinter as tk
from pathlib import Path
import datetime
import os 
from ruamel.yaml import YAML

def recordWebcamVideos(session):
    #%% -----------------------------------------------SESSION INFO
    #Choose a file path   
    userPath = '' #add custom path here if desired as r'[filepath]\', and for right now **you should have two backslashes at the end of your path**
    if not userPath:
            filepath = Path.cwd()
    else: 
            filepath = userPath

    #create session ID        
    sessionID_in = datetime.datetime.now().strftime("sesh_%y-%m-%d_%H%M%S")
    session.sessionID = sessionID_in
    
    #load the parameters YAML and extract the saved parameters if possible, and the default otherwise
    parameter_path = filepath/'parameters.yaml'
    parameters_yaml = YAML()
    parameters = parameters_yaml.load(parameter_path)

    try: 
        rotation_entry = parameters['saved']['rotations']
        parameter_entry = parameters['saved']['parameters']
    except:
        print("Using Default Config")
        rotation_entry = parameters['default']['rotations']
        parameter_entry = parameters['default']['parameters']        
    #---------------------------------------------Run With GUI    

    #run the GUI to get the tasks, the cams chosen, the camera settings, and the session ID
    task, cam_inputs, rotDict, paramDict, session.sessionID = recordGUI.RunGUI(sessionID_in,rotation_entry,parameter_entry)
    

    #update the saved parameters in the YAML
    parameters['saved']['rotations'] = rotDict
    parameters['saved']['parameters'] = paramDict
    parameters_yaml.dump(parameters, parameter_path)
    
    #create a list from the rotation dictionary to be used in running webcams
    rotation_input = list(rotDict.values())

    proceedToCalibration = ''   
    # %% TASK CHOICES

    #-----------------------------------------------SETUP
    #when testing, press 'escape' to individually exit each feed. Camera input number associated with feed is displayed up top
            
    if task == 'setup': #don't change this boolean by accident pls
        
        if not cam_inputs:
                raise ValueError('Camera input list (cam_inputs) is empty')

        camsetup.RunSetup(cam_inputs,rotation_input,paramDict)
        continueToRecording,session.sessionID = recordGUI.RunProceedtoRecordGUI(sessionID_in)

        #proceedToCalibration = ''    

        if continueToRecording: 
            config_yaml_path = recordingconfig.createSession(session,filepath)
            recordingconfig.createSessionTxt(session,paramDict,rotDict)
            proceedToCalibration = runrecordingprocess.RunCams(session,cam_inputs,paramDict,rotation_input) #press ESCAPE to end the recording

    #-----------------------------------------------RECORD
    #Press ESCAPE to stop the recording process, and continue onto the time-syncing/editing process

    elif task == 'record':#don't change this boolean by accident pls
    #if continueToRecording:    
        #create a recording session
        config_yaml_path = recordingconfig.createSession(session,filepath)
        recordingconfig.createSessionTxt(session,paramDict,rotDict)

        #check that cams were chosen (these lines can be removed when we make it mandatory to use the GUI)
        if not cam_inputs:
            raise ValueError('Camera input list (cam_inputs) is empty')
            
        #run the recording webcams and get back a table of results    
        proceedToCalibration = runrecordingprocess.RunCams(session,cam_inputs,paramDict,rotation_input) #press ESCAPE to end the recording


    elif not task:
        print('No task detected')


    elif task == 'debug': #out-of-order for right now
        #to debug, manually enter a sessionID and change the task, and the results table/figures from that session will be generated
        recordPath = filepath/'Data'/sessionID
        webcam.DebugTime(sessionID,recordPath)

       
    return proceedToCalibration

#if __name__ == "__main__":
#    runCams()