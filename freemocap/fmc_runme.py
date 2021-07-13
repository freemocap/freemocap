from freemocap import (
    createvideo,
    recordingconfig,
    runcams,
    runmeGUI,
    calibrate,
    fmc_mediapipe,
    fmc_openpose,
    fmc_deeplabcut,
    reconstruct3D,
    playskeleton,
    session,
    webcamGUI
)
from freemocap.fmc_pyqtgraph import PlayerDockedWindow

from pathlib import Path
import os

from aniposelib.boards import CharucoBoard

import numpy as np

from ruamel.yaml import YAML

def Run(sessionID=None,stage=1,useOpenPose=True,useMediaPipe=False,useDLC=True,dlcConfigPath=None,debug=False,setDataPath=False):
    sesh = session.Session()

    sesh.sessionID = sessionID
    sesh.useOpenPose= useOpenPose
    sesh.useMediaPipe = useMediaPipe
    sesh.useDLC= useDLC
    sesh.debug = debug
    sesh.setDataPath = setDataPath

    sesh.dataFolderName = 'FreeMocap_Data'

    if sesh.useDLC: 
        import deeplabcut as dlc
        sesh.dlcConfigPath =dlcConfigPath
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
            basePath = runmeGUI.RunChooseDataPathGUI(session)
            #sesh.dataFolderPath = Path(basePath)/sesh.dataFolderName
        else:
            here = Path(__file__).parent
            preferences_path = here/'user_preferences.yaml'
            preferences_yaml = YAML()
        
            if not preferences_path.exists():
                raise FileNotFoundError('The user preferences yaml could not be located. Please change setDataPath to True to manually set the path to the Data folder')
        
            preferences = preferences_yaml.load(preferences_path)
            current_path_to_data = preferences['saved']['path_to_save']
            basePath = current_path_to_data
        dataFolder = Path(basePath)/sesh.dataFolderName
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
                        square_length = 82,#regular boi charuco
                        marker_length = 65,
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
        sesh.cgroup, sesh.mean_charuco_fr_mar_dim = calibrate.CalibrateCaptureVolume(sesh,board)
    else:
        print('Skipping Calibration')

    # %% Stage Four
    if stage <= 4:
        print('Starting Track Image Points')
        if sesh.useMediaPipe:
            fmc_mediapipe.runMediaPipe(sesh)
            sesh.mediaPipeData_nCams_nFrames_nImgPts_XYC = fmc_mediapipe.parseMediaPipe(sesh)
            sesh.mediaPipeSkel_fr_mar_dim = reconstruct3D.reconstruct3D(sesh,sesh.mediaPipeData_nCams_nFrames_nImgPts_XYC, confidenceThreshold=.1)
            np.save(sesh.dataArrayPath/'mediaPipeSkel_3d.npy', sesh.mediaPipeSkel_fr_mar_dim) #save data to npy

        if sesh.useOpenPose:
            fmc_openpose.runOpenPose(sesh, dummyRun=False)
            sesh.openPoseData_nCams_nFrames_nImgPts_XYC = fmc_openpose.parseOpenPose(sesh)
            sesh.openPoseSkel_fr_mar_dim = reconstruct3D.reconstruct3D(sesh,sesh.openPoseData_nCams_nFrames_nImgPts_XYC, confidenceThreshold=.1)
            np.save(sesh.dataArrayPath/'openPoseSkel_3d.npy', sesh.openPoseSkel_fr_mar_dim) #save data to npy

        sesh.syncedVidList = []
        if sesh.useDLC:
            for vid in sesh.syncedVidPath.glob('*.mp4'):
                sesh.syncedVidList.append(str(vid))
            
            dlc.analyze_videos(sesh.dlcConfigPath,sesh.syncedVidList, destfolder= sesh.dlcDataPath, save_as_csv=True) 

            sesh.dlcData_nCams_nFrames_nImgPts_XYC = fmc_deeplabcut.parseDeepLabCut(sesh)
            sesh.dlc_fr_mar_dim = reconstruct3D.reconstruct3D(sesh,sesh.dlcData_nCams_nFrames_nImgPts_XYC, confidenceThreshold=.95)
            np.save(sesh.dataArrayPath/'deepLabCut_3d.npy', sesh.dlc_fr_mar_dim) #save data to npy
        sesh.save_session()
    else:
        print('Skipping Run MediaPipe')

    # # %% Stage Five
    # if not stage > 5:
    #     print('Starting Parse MediaPipe')
    #     sesh.mediaPipeData_nCams_nFrames_nImgPts_XYC = fmc_mediapipe.parseMediaPipe(sesh)
    # else:
    #     print('Skipping Parse MediaPipe')
        


    # # %% Stage Six
    # if not stage > 6:
    #     print()
    #     print('Starting Skeleton Reconstruction')
    #     sesh.skel_fr_mar_dim = reconstruct3D.reconstruct3D(sesh,sesh.mediaPipeData_nCams_nFrames_nImgPts_XYC, confidenceThreshold=.1)

    #     path_to_skel_points = sesh.dataArrayPath/'skeleton_points.npy'
    #     np.save(path_to_skel_points, sesh.skel_fr_mar_dim)
    # else:
    #     print('Skipping Skeleton Reconstruction')
    


    #reupdate the config_settings with mediapipe and openpose image paths
    #sesh.config_settings = recordingconfig.load_config_yaml(sesh.yamlPath)


    # %% Stage Six
    if stage <= 6:
        print ('Starting PyQT Animation')
        createvideo.createBodyTrackingVideos(sesh)
        displayVid = 1  
        #if displayVid = 0, will show the synced videos
        #if displayVid = 1, will show the openPosed videos
        playWin = PlayerDockedWindow(sesh,displayVid)
        playWin.animate()

    # %% Stage Seven
    if stage <= 7:
        print('Starting Skeleton Plotting')
        playskeleton.ReplaySkeleton_matplotlib(
                                    sesh,
                                    vidType=1,
                                    startFrame=40,
                                    azimuth=-90, 
                                    elevation=-80,
                                    useOpenPose=sesh.useOpenPose,
                                    useMediaPipe=sesh.useMediaPipe,
                                    useDLC=sesh.useDLC)
        # fmc_pyqtgraph.PlaySkeleton(
        #                             sesh,
        #                             vidType=1,
        #                             startFrame=40,
        #                             azimuth=-90, 
        #                             elevation=-80,
        #                             useOpenPose=useOpenPose,
        #                             useMediaPipe=useMediaPipe,
        #                             useDLC=useDLC)

        # playSkel = PlaySkeleton(sesh)
        # playSkel.animate()
        #playWin =PlayerDockedWindow(sesh)
        #playWin.animate()

    else:
        print('Skipping Skeleton Plotting')




    # %% Stage Eight
    if stage <= 8:
        print()
        print('Starting Video Creation')
        createvideo.createVideo(sesh)
    else:
        print('Skipping Video Creation')
        

