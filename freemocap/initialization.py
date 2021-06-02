
from pathlib import Path
from ruamel.yaml import YAML
import datetime
import sys
import pandas as pd
import numpy as np

from freemocap.webcam import recordGUI,camsetup
from freemocap import recordingconfig, stolenfromanipose

def initialize(session, stage, board):

    print('Starting initialization for stage {}'.format(stage))
    #if stage == 1:    
    filepath = Path.cwd()
# %% Stage One Initialization
    if stage == 1:

        
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

        proceedToRecording = False #create this boolean, set it to false, and if the user wants to record
                                   #later in the pipeline, it will be set to true

    #run the GUI to get the tasks, the cams chosen, the camera settings, and the session ID
        task, cam_inputs, rotDict, paramDict, session.sessionID = recordGUI.RunGUI(sessionID_in,rotation_entry,parameter_entry)
    
    #update the saved parameters in the YAML
        parameters['saved']['rotations'] = rotDict
        parameters['saved']['parameters'] = paramDict
        parameters_yaml.dump(parameters, parameter_path)
        
    #create a list from the rotation dictionary to be used in running webcams
        rotation_input = list(rotDict.values())

        if task == 'setup':
            #run setup processes, and then check if th user wants to proceed to recording 
            camsetup.RunSetup(cam_inputs,rotation_input,paramDict)
            proceedToRecording,session.sessionID = recordGUI.RunProceedtoRecordGUI(sessionID_in)

        elif task == 'record':
            proceedToRecording = True
        
        if proceedToRecording:
            #create these session properties to be used later in the pipeline
            session.cam_inputs = cam_inputs
            session.parameterDictionary = paramDict
            session.rotationInputs = rotation_input

            #create a config yaml and text file for this session
            config_yaml_path = recordingconfig.createSession(session,filepath)
            recordingconfig.createSessionTxt(session,paramDict,rotDict)
            
            print('Proceeding to Stage One')        
    
        else:
        
            sys.exit('Recording Cancelled')
# %% Stage Two Initalization
    if stage == 2:
        session.sessionPath = filepath/'Data'/session.sessionID #create a session path based on the sessionID

        #load the config yaml for this session, and add all the paths to the session file
        session.yamlPath = session.sessionPath/'{}_config.yaml'.format(session.sessionID)
        session.config_settings = recordingconfig.load_config_yaml(session.yamlPath) #config settings = paths and camera parameter inputs
        recordingconfig.load_session_paths(session,session.config_settings) #add paths to session class

        #from the config settings add the camera input parameters to parameter dictionary
        session.parameterDictionary = session.config_settings['CamInputs']['ParameterDict']
        session.rotationInputs = session.config_settings['CamInputs']['RotationInputs']

        #initialize the path to the timestamp csv
        csvName = session.sessionID + '.csv'
        csvPath = session.sessionPath/csvName

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


        #initialize all the session variables we'll need to run the rest of the pipeline
        session.timeStampData = timeStampData
        session.camIDs = camIDs
        session.numCamRange = numCamRange
        session.vidNames = vidNames
        session.numCams = numCams

    if stage == 3:
       
        session.sessionPath = filepath/'Data'/session.sessionID #create a session path based on the sessionID

        #load the config yaml for this session, and add all the paths to the session file
        session.yamlPath = session.sessionPath/'{}_config.yaml'.format(session.sessionID)

        if session.yamlPath.is_file(): #if the config yaml exists (from a webcam recording)
            session.config_settings = recordingconfig.load_config_yaml(session.yamlPath) #config settings = paths and camera parameter inputs
            recordingconfig.load_session_paths(session,session.config_settings) #add paths to session class
        else: #if it doesn't exist (because of a GoPro/external camera recording)
            recordingconfig.createSession(session,filepath)

    if stage == 4:

        session.sessionPath = filepath/'Data'/session.sessionID

        session.yamlPath = session.sessionPath/'{}_config.yaml'.format(session.sessionID) #path to the configuration yaml
        session.config_settings = recordingconfig.load_config_yaml(session.yamlPath) #config settings = paths and camera parameter inputs
        recordingconfig.load_session_paths(session,session.config_settings) #add paths to session class

        for count,thisVidPath in enumerate(session.syncedVidPath.glob('*.mp4'),start=1): 
            session.numCams = count
        
        

    if stage == 5:

        session.sessionPath = filepath/'Data'/session.sessionID

        session.yamlPath = session.sessionPath/'{}_config.yaml'.format(session.sessionID) #path to the configuration yaml
        session.config_settings = recordingconfig.load_config_yaml(session.yamlPath) #config settings = paths and camera parameter inputs
        recordingconfig.load_session_paths(session,session.config_settings) #add paths to session class

        for count,thisVidPath in enumerate(session.syncedVidPath.glob('*.mp4'),start=1): 
            session.numCams = count

        session.openPose_jsonPathList = session.config_settings['openPose_jsonPathList']
        session.numCams = len(session.openPose_jsonPathList)

    if stage == 6:

        session.sessionPath = filepath/'Data'/session.sessionID

        session.yamlPath = session.sessionPath/'{}_config.yaml'.format(session.sessionID) #path to the configuration yaml
        session.config_settings = recordingconfig.load_config_yaml(session.yamlPath) #config settings = paths and camera parameter inputs
        recordingconfig.load_session_paths(session,session.config_settings) #add paths to session class

        session.openPoseData_nCams_nFrames_nImgPts_XY = np.load(session.dataArrayPath/'openPoseData_nCams_nFrames_nImgPts_XY.npy')
        

    if stage == 7:

        session.sessionPath = filepath/'Data'/session.sessionID

        session.yamlPath = session.sessionPath/'{}_config.yaml'.format(session.sessionID) #path to the configuration yaml
        session.config_settings = recordingconfig.load_config_yaml(session.yamlPath) #config settings = paths and camera parameter inputs
        recordingconfig.load_session_paths(session,session.config_settings) #add paths to session class   

        session.openPose_imgPathList = session.config_settings['openPose_imgPathList']
        session.numCams = len(session.openPose_imgPathList)

        session.mean_charuco_fr_mar_dim = np.load(session.dataArrayPath/'charuco_points.npy')
        session.skel_fr_mar_dim = np.load(session.dataArrayPath/'skeleton_points.npy')

    if stage == 8:

        session.sessionPath = filepath/'Data'/session.sessionID

        session.yamlPath = session.sessionPath/'{}_config.yaml'.format(session.sessionID) #path to the configuration yaml
        session.config_settings = recordingconfig.load_config_yaml(session.yamlPath) #config settings = paths and camera parameter inputs
        recordingconfig.load_session_paths(session,session.config_settings) #add paths to session class   

# %%
