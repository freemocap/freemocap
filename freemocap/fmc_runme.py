from freemocap import (
    recordingconfig,
    runcams,
    runmeGUI,
    calibrate,
    fmc_mediapipe,
    fmc_openpose,
    fmc_deeplabcut,
    reconstruct3D,
    play_skeleton_animation,
    session,
    webcamGUI
)


from pathlib import Path
import os

from aniposelib.boards import CharucoBoard

import numpy as np

from ruamel.yaml import YAML

def RunMe(sessionID=None,
        stage=1,
        useOpenPose=False, 
        runOpenPose = True, 
        useMediaPipe=True,
        runMediaPipe=True,
        useDLC=False,
        dlcConfigPath=None,
        debug=False,
        setDataPath = False,
        userDataPath = None,
        recordVid = True,
        reconstructionConfidenceThreshold = .7,
        charucoSquareSize = 36,#mm - ~the size of the squares when printed on 8.5x11" paper based on parameters in ReadMe.md
        calVideoFrameLength = 120,
        ):
    """ 
    Starts the freemocap pipeline based on either user-input values, or default values. Creates a new session class instance (called sesh)
    based on the specified inputs. Checks for previous user preferences and choices if they exist, or will prompt the user for new choices
    if they don't. Runs the initialization for the system and runs each stage of the pipeline.
    """ 
    sesh = session.Session()

    sesh.sessionID = sessionID
    sesh.useOpenPose= useOpenPose
    sesh.useMediaPipe = useMediaPipe
    sesh.useDLC= useDLC
    sesh.debug = debug
    sesh.setDataPath = setDataPath
    sesh.userDataPath = userDataPath
    sesh.dataFolderName = recordingconfig.dataFolder

    if sesh.useDLC and stage < 5: 
        import deeplabcut as dlc
    #    sesh.dlcConfigPath = dlcConfigPath



    #%% load user preferences if they exist, create a new preferences yaml if they don't
    here = Path(__file__).parent
    preferences_path = here/'user_preferences.yaml'
    preferences_yaml = YAML()

    if preferences_path.exists():
        preferences = preferences_yaml.load(preferences_path)
    else:
        preferences = recordingconfig.parameters_for_yaml
        preferences_yaml.dump(preferences, preferences_path)
    
    sesh.preferences = preferences
    sesh.preferences_path = preferences_path
        

    if sesh.useDLC and stage < 5:

        try:
            saved_dlc_paths = preferences['saved']['dlc_config_paths']
        except: 
            saved_dlc_paths = preferences['default']['dlc_config_paths']


        dlc_config_paths = runmeGUI.RunChooseDLCPathGUI(sesh,saved_dlc_paths)
        

        sesh.preferences['saved']['dlc_config_paths'] = dlc_config_paths
        sesh.save_user_preferences(sesh.preferences)

        # sesh.dlcConfigPath = Path("C:\\Users\\jonma\\Dropbox\\GitKrakenRepos\\freemocap\\DLC_Models\\PinkGreenRedJugglingBalls-JSM-2021-05-31\\config.yaml")
        #sesh.dlcConfigPath = Path("C:\\Users\\jonma\\Desktop\\freemocap\\DLC_Models\\PinkGreenRedJugglingBalls-JSM-2021-05-31\\config.yaml") 
    if stage > 1:
        #if we are rerunning a session folder
        # 1) Check if we're using the last saved dataFolderPath, or if the user wants to choose a different one
        #   a. if the user wants to choose one, bring up a GUI to let them decide
        #   b. if we're using the last known path - parse the user preferences yaml (and check if that yaml exists)
        # 2) Check that the data folder exists
        # 3) If no sessionID was user-input, search the chosen directory for the last session created
        if sesh.setDataPath == True:
            sesh.basePath = runmeGUI.RunChooseDataPathGUI(session)
            sesh.basePath = Path(sesh.basePath)
            #sesh.dataFolderPath = Path(basePath)/sesh.dataFolderName

        elif sesh.userDataPath is not None:
            sesh.basePath = sesh.userDataPath
        else:
            try:
                current_path_to_data = preferences['saved']['path_to_save']
                sesh.basePath = current_path_to_data
            except KeyError:
                print('Saved Data path not found, please choose a new one')
                sesh.basePath = runmeGUI.RunChooseDataPathGUI(session)
                sesh.preferences['saved']['path_to_save'] = str(sesh.basePath)
                sesh.save_user_preferences(sesh.preferences)


        dataFolder = Path(sesh.basePath)/sesh.dataFolderName
        sesh.dataFolderPath = dataFolder
        
        if not dataFolder.exists():
            raise FileNotFoundError('No data folder located at: ' + str(dataFolder))

        if sesh.sessionID == None:    
            subfolders = [f.path for f in os.scandir(sesh.dataFolderPath) if f.is_dir()]  # copy-pasta from who knows where
            sesh.sessionID = Path(subfolders[-1]).stem  # grab the name of the last folder in the list of subfolders
        
        print('Running ' + str(sesh.sessionID) + ' from ' + str(sesh.dataFolderPath))
        
        # if sesh. setDataPath == True:
        #     #run file dialog GUI (select folder where the data folder)
        # here = Path(__file__).parent
        # parameter_path = here/'user_preferences.yaml'
        # if parameter_path.exists(): 
        #     #this section looks for the Data folder at the last saved path from the user_preferences.yaml, if none exists, it raises an error
        #     #if not, if finds the most recent session from that Data folder 
        #     parameters_yaml = YAML()
        #     parameters = parameters_yaml.load(parameter_path)
        #     current_path_to_data = parameters['saved']['path_to_save']
        #     dataFolder = Path(current_path_to_data)/'Data' 
        #     try:
        #         subfolders = [f.path for f in os.scandir(dataFolder) if f.is_dir()]  # copy-pasta from who knows where
        #         sesh.sessionID = Path(subfolders[-1]).stem  # grab the name of the last folder in the list of subfolders
        #     except FileNotFoundError:
        #        raise FileNotFoundError('No data folder located at: ' + str(dataFolder))
            
        #     print('Running ' + str(sesh.sessionID) + ' from ' + str(dataFolder))
        #     sesh.dataPath = dataFolder
    
    
    
    #else: #First time run! Make 'FreeMoCap_Data' Folder (and eventually,  prompt to download sample data)
    #    dataFolder.mkdir()
    #    sampleDataFolder = dataFolder / '_sample_data_folder'
    #    sampleDataFolder.mkdir()

    board = CharucoBoard(7, 5,
                        #square_length=1, # here, in mm but any unit works (JSM NOTE - just using '1' so resulting units will be in 'charuco squarelenghts`)
                        #marker_length=.8,
                        #  square_length = 121, #big boi charuco
                        #  marker_length = 98,
                        square_length = charucoSquareSize,#mm
                        marker_length = charucoSquareSize*.8,#mm
                        marker_bits=4, dict_size=250)


    sesh.board = board
    #sesh.input_stage = stage



    # %% Initialization
    #sesh.initialize(stage)
    if stage ==2 or stage == 1:
        webcamGUI.initialize(sesh,stage,board)
    else:
        sesh.initialize(stage)

    # %% Stage One
    if stage <= 1:
        print()
        print('Starting Video Recordings')
        runcams.RecordCams(sesh, sesh.cam_inputs, sesh.parameterDictionary, sesh.rotationInputs)
        sesh.save_session()
    else:
        print('Skipping Video Recording')


    # %% Stage Two
    if stage <= 2:
        print()
        print('Starting Video Syncing')
        runcams.SyncCams(sesh, sesh.timeStampData,sesh.numCamRange,sesh.vidNames,sesh.camIDs)
        sesh.save_session()
    else:
        print('Skipping Video Syncing')

    # %% Stage Three
    if stage <= 3:
        print()
        print('Starting Calibration')
        sesh.cgroup, sesh.mean_charuco_fr_mar_xyz = calibrate.CalibrateCaptureVolume(sesh,board, calVideoFrameLength)
    else:
        print('Skipping Calibration')

    # %% Stage Four
    if stage <= 4:

        print('Starting Track Image Points')
        if sesh.useMediaPipe:
            if runMediaPipe:
                fmc_mediapipe.runMediaPipe(sesh)

            sesh.mediaPipeData_nCams_nFrames_nImgPts_XYC = fmc_mediapipe.parseMediaPipe(sesh)
            sesh.mediaPipeSkel_fr_mar_xyz, sesh.mediaPipeSkel_reprojErr = reconstruct3D.reconstruct3D(sesh,sesh.mediaPipeData_nCams_nFrames_nImgPts_XYC, confidenceThreshold=reconstructionConfidenceThreshold)
            np.save(sesh.dataArrayPath/'mediaPipeSkel_3d.npy', sesh.mediaPipeSkel_fr_mar_xyz) #save data to npy
            np.save(sesh.dataArrayPath/'mediaPipeSkel_reprojErr.npy', sesh.mediaPipeSkel_reprojErr) #save data to npy            
        sesh.save_session()

        if sesh.useOpenPose:
            fmc_openpose.runOpenPose(sesh, runOpenPose=runOpenPose)
            sesh.openPoseData_nCams_nFrames_nImgPts_XYC = fmc_openpose.parseOpenPose(sesh)
            sesh.openPoseSkel_fr_mar_xyz, sesh.openPoseSkel_reprojErr = reconstruct3D.reconstruct3D(sesh,sesh.openPoseData_nCams_nFrames_nImgPts_XYC, confidenceThreshold=reconstructionConfidenceThreshold)
            np.save(sesh.dataArrayPath/'openPoseSkel_3d.npy', sesh.openPoseSkel_fr_mar_xyz) #save data to npy
            np.save(sesh.dataArrayPath/'openPoseSkel_reprojErr.npy', sesh.openPoseSkel_reprojErr) #save data to npy
        sesh.save_session()
        sesh.syncedVidList = []
        if sesh.useDLC:
            for vid in sesh.syncedVidPath.glob('*.mp4'):
                sesh.syncedVidList.append(str(vid))
            
            for config_path in dlc_config_paths:
                dlc.analyze_videos(config_path,sesh.syncedVidList, destfolder= sesh.dlcDataPath, save_as_csv=True) 
                sesh.dlcData_nCams_nFrames_nImgPts_XYC = fmc_deeplabcut.parseDeepLabCut(sesh, config_path)
                sesh.dlc_fr_mar_xyz, sesh.dlc_reprojErr = reconstruct3D.reconstruct3D(sesh,sesh.dlcData_nCams_nFrames_nImgPts_XYC, confidenceThreshold=reconstructionConfidenceThreshold)
                np.save(sesh.dataArrayPath/'deepLabCut_3d.npy', sesh.dlc_fr_mar_xyz) #save data to npy
                np.save(sesh.dataArrayPath/'deepLabCut_reprojErr.npy', sesh.dlc_reprojErr) #save data to npy
        sesh.save_session()
    else:
        print('Skipping Run MediaPipe')

    # %% Stage Five - Make Skreleton Animation
    if stage <= 5:
        print('Starting Skeleton Plotting')
        play_skeleton_animation.PlaySkeletonAnimation(
                                sesh,
                                startFrame=0,
                                azimuth=-90,
                                elevation=-81,
                                useOpenPose=useOpenPose,
                                useMediaPipe=useMediaPipe,
                                useDLC=useDLC,
                                recordVid = recordVid
                                )
        # print ('Starting PyQT Animation')
        # createvideo.createBodyTrackingVideos(sesh)
        # displayVid = 1  
        # #if displayVid = 0, will show the synced videos
        # #if displayVid = 1, will show the openPosed videos
        # playWin = PlayerDockedWindow(sesh,displayVid)
        # playWin.animate()

    else:
        print('Skipping Skeleton Plotting')



        

