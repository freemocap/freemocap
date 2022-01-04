from pathlib import Path
import datetime
import sys
import pandas as pd
import numpy as np

from freemocap.webcam import recordGUI, camsetup
from freemocap import recordingconfig, fmc_anipose
from rich.console import Console

console = Console()

def initialize(session, stage, board):
    """ 
    Runs the initialization needed to start a new recording from scratch (Stage 1)
    Create a new sessionID and attempt to load previous recording parameters (camera settings/rotations/save locations), 
    and use default values if previous parameters are not found. Ask user to select preferences using a series of GUIs, runs the Setup option if 
    chosen by the user, and ultimately sets a bool that dictates whether we should proceed to start the actual Stage 1 recording. Also saves parameters
    into the session class, which gets saved into the user_preferences yaml

    """ 
    
    console.rule(style="color({})".format(13))    
    console.rule('Finding available webcams',style="color({})".format(13))
    console.rule(style="color({})".format(13)) 

    # if stage == 1:
    filepath = Path.cwd()

    session.board = board

    # %% Stage One Initialization


    # create session ID
    sessionID_in = datetime.datetime.now().strftime("sesh_%Y-%m-%d_%H_%M_%S")
    session.sessionID = sessionID_in

#load the parameters YAML and extract the saved parameters if possible, and the default otherwise       
    #here = Path(__file__).parent
    # parameter_path = here/'user_preferences.yaml'
    # parameters_yaml = YAML()
    # if parameter_path.exists():
    #     parameters = parameters_yaml.load(parameter_path)
    # else:
    #     parameters = recordingconfig.parameters_for_yaml
    #     with open(parameter_path,'w') as outfile:
    #         parameters_yaml.dump(parameters, outfile)




    proceedToRecording = False #create this boolean, set it to false, and if the user wants to record
                                #later in the pipeline, it will be set to true

#run the GUI to get the tasks, the cams chosen, the camera settings, and the session ID
    cam_inputs, task = recordGUI.RunChoiceGUI()
    restartSetup = True

    while restartSetup == True:
        
        try:
            rotation_entry = session.preferences["saved"]["rotations"]
            parameter_entry = session.preferences["saved"]["parameters"]
        except:
            print("Could not load saved parameters, using default parameters")
            rotation_entry = session.preferences['default']['rotations']
            parameter_entry = session.preferences['default']['parameters']
                

        try:
            current_path_to_save = session.preferences['saved']['path_to_save']
        except:
            current_path_to_save = session.preferences['default']['path_to_save'] 
        rotDict, paramDict, session.sessionID,savepath, mediaPipeOverlay = recordGUI.RunParametersGUI(sessionID_in, rotation_entry, parameter_entry, current_path_to_save, cam_inputs, task)
    
    #update the saved parameters in the YAML
        #recordingconfig.rotation_settings['saved'] = rotDict
        #recordingconfig.camera_session.preferences['saved'] = paramDict
        session.preferences['saved']['rotations'] = rotDict
        session.preferences['saved']['parameters'] = paramDict
        if savepath is not None:
            session.preferences['saved']['path_to_save'] = savepath

        session.save_user_preferences(session.preferences)

    #save recording parameters to the config yaml

        
    #create a list from the rotation dictionary to be used in running webcams
        rotation_input = list(rotDict.values())

        if task == "setup":
            # run setup processes, and then check if th user wants to proceed to recording
            camsetup.RunSetup(cam_inputs, rotation_input, paramDict,mediaPipeOverlay)
            proceedToRecording, restartSetup, session.sessionID, savepath = recordGUI.RunProceedtoRecordGUI(
                sessionID_in,current_path_to_save
            )
            session.preferences['saved']['path_to_save'] = savepath
            session.save_user_preferences(session.preferences)
        elif task == "record":
            proceedToRecording = True
            restartSetup = False

    if proceedToRecording:
        # create these session properties to be used later in the pipeline
        session.cam_inputs = cam_inputs
        session.parameterDictionary = paramDict
        session.rotationInputs = rotation_input
        session.basePath = Path(savepath)

        #create a config yaml and text file for this session
        session.start_session(session.parameterDictionary,session.rotationInputs)
        session.session_settings['recording_parameters']['RotationInputs'] = rotDict
        session.session_settings['recording_parameters']['ParameterDict'] = paramDict
        #configyaml = YAML()
        #sessionsettings = configyaml.load(session.session_yaml_path)
        #sessionsettings['recording_parameters']['RotationInputs'] = rotDict
        #sessionsettings['recording_parameters']['ParameterDict'] = paramDict
        #configyaml.dump(sessionsettings, session.session_yaml_path)
        #print(sessionsettings)
        #config_yaml_path = recordingconfig.createSession(session,filepath)
        #recordingconfig.createSessionTxt(session,paramDict,rotDict)
        
        print('Proceeding to Stage One')        

    else:
    
        sys.exit('Recording Canceled')
