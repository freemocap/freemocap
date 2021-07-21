from pathlib import Path
from ruamel.yaml import YAML
import datetime
import sys
import pandas as pd
import numpy as np

from freemocap.webcam import recordGUI, camsetup
from freemocap import recordingconfig, fmc_anipose


def initialize(session, stage, board):

    print("Starting initialization for stage {}".format(stage))
    # if stage == 1:
    filepath = Path.cwd()

    session.board = board

    # %% Stage One Initialization
    if stage == 1:

        # create session ID
        sessionID_in = datetime.datetime.now().strftime("sesh_%y-%m-%d_%H%M%S")
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


        proceedToRecording = False #create this boolean, set it to false, and if the user wants to record
                                   #later in the pipeline, it will be set to true

    #run the GUI to get the tasks, the cams chosen, the camera settings, and the session ID
        task, cam_inputs, rotDict, paramDict, session.sessionID,savepath = recordGUI.RunGUI(sessionID_in,rotation_entry,parameter_entry,current_path_to_save)
    
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
            camsetup.RunSetup(cam_inputs, rotation_input, paramDict)
            proceedToRecording, session.sessionID, savepath = recordGUI.RunProceedtoRecordGUI(
                sessionID_in,current_path_to_save
            )
            session.preferences['saved']['path_to_save'] = savepath
            session.save_user_preferences(session.preferences)
        elif task == "record":
            proceedToRecording = True

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
# %% Stage Two Initalization
    if stage == 2:
        # session.sessionPath = filepath/'Data'/session.sessionID #create a session path based on the sessionID

        # #load the config yaml for this session, and add all the paths to the session file
        # session.yamlPath = session.sessionPath/'{}_config.yaml'.format(session.sessionID)
        # session.config_settings = recordingconfig.load_config_yaml(session.yamlPath) #config settings = paths and camera parameter inputs
        # recordingconfig.load_session_paths(session,session.config_settings) #add paths to session class
        session.initialize(stage)

        #from the config settings add the camera input parameters to parameter dictionary
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


        #initialize all the session variables we'll need to run the rest of the pipeline
        session.timeStampData = timeStampData
        session.camIDs = camIDs
        session.numCamRange = numCamRange
        session.vidNames = vidNames
        session.numCams = numCams

    if stage == 3:

        session.sessionPath = (
            filepath / "Data" / session.sessionID
        )  # create a session path based on the sessionID

        # load the config yaml for this session, and add all the paths to the session file
        session.yamlPath = session.sessionPath / "{}_config.yaml".format(
            session.sessionID
        )

        if (
            session.yamlPath.is_file()
        ):  # if the config yaml exists (from a webcam recording)
            session.config_settings = recordingconfig.load_config_yaml(
                session.yamlPath
            )  # config settings = paths and camera parameter inputs
            recordingconfig.load_session_paths(
                session, session.config_settings
            )  # add paths to session class
        else:  # if it doesn't exist (because of a GoPro/external camera recording)
            recordingconfig.createSession(session, filepath)

    if stage == 4:

        session.sessionPath = filepath / "Data" / session.sessionID

        session.yamlPath = session.sessionPath / "{}_config.yaml".format(
            session.sessionID
        )  # path to the configuration yaml
        session.config_settings = recordingconfig.load_config_yaml(
            session.yamlPath
        )  # config settings = paths and camera parameter inputs
        recordingconfig.load_session_paths(
            session, session.config_settings
        )  # add paths to session class

        for count, thisVidPath in enumerate(
            session.syncedVidPath.glob("*.mp4"), start=1
        ):
            session.numCams = count

    if stage == 6:

        session.sessionPath = filepath / "Data" / session.sessionID

        session.yamlPath = session.sessionPath / "{}_config.yaml".format(
            session.sessionID
        )  # path to the configuration yaml
        session.config_settings = recordingconfig.load_config_yaml(
            session.yamlPath
        )  # config settings = paths and camera parameter inputs
        recordingconfig.load_session_paths(
            session, session.config_settings
        )  # add paths to session class

        if session.useOpenPose:
            session.openPose_imgPathList = session.config_settings[
                "openPose_imgPathList"
            ]

        if session.useMediaPipe:
            session.mediaPipe_imgPathList = session.config_settings[
                "mediaPipe_imgPathList"
            ]

    # if stage == 5:

    #     session.sessionPath = filepath/'Data'/session.sessionID

    #     session.yamlPath = session.sessionPath/'{}_config.yaml'.format(session.sessionID) #path to the configuration yaml
    #     session.config_settings = recordingconfig.load_config_yaml(session.yamlPath) #config settings = paths and camera parameter inputs
    #     recordingconfig.load_session_paths(session,session.config_settings) #add paths to session class

    #     for count,thisVidPath in enumerate(session.syncedVidPath.glob('*.mp4'),start=1):
    #         session.numCams = count

    #     session.mediaPipe_jsonPathList = session.config_settings['mediaPipe_jsonPathList']
    #     session.numCams = len(session.mediaPipe_jsonPathList)

    # if stage == 6:

    #     session.sessionPath = filepath/'Data'/session.sessionID

    #     session.yamlPath = session.sessionPath/'{}_config.yaml'.format(session.sessionID) #path to the configuration yaml
    #     session.config_settings = recordingconfig.load_config_yaml(session.yamlPath) #config settings = paths and camera parameter inputs
    #     recordingconfig.load_session_paths(session,session.config_settings) #add paths to session class

    #     session.mediaPipeData_nCams_nFrames_nImgPts_XY = np.load(session.dataArrayPath/'mediaPipeData_nCams_nFrames_nImgPts_XY.npy')

    if stage == 7:

        session.sessionPath = filepath / "Data" / session.sessionID

        session.yamlPath = session.sessionPath / "{}_config.yaml".format(
            session.sessionID
        )  # path to the configuration yaml
        session.config_settings = recordingconfig.load_config_yaml(
            session.yamlPath
        )  # config settings = paths and camera parameter inputs
        recordingconfig.load_session_paths(
            session, session.config_settings
        )  # add paths to session class

        session.mediaPipe_imgPathList = session.config_settings["mediaPipe_imgPathList"]
        session.openPose_imgPathList = session.config_settings["openPose_imgPathList"]

        # session.openPose_imgPathList = session.config_settings['openPose_imgPathList']
        # session.numCams = len(session.openPose_imgPathList)

    if stage == 8:

        session.sessionPath = filepath / "Data" / session.sessionID

        session.yamlPath = session.sessionPath / "{}_config.yaml".format(
            session.sessionID
        )  # path to the configuration yaml
        session.config_settings = recordingconfig.load_config_yaml(
            session.yamlPath
        )  # config settings = paths and camera parameter inputs
        recordingconfig.load_session_paths(
            session, session.config_settings
        )  # add paths to session class


# %%
