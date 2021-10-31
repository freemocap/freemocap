
from freemocap.fmc_startup import startup, startupGUI
from freemocap.webcam import camera_settings, timesync

from pathlib import Path
import os
import subprocess
import time 
from aniposelib.boards import CharucoBoard

import numpy as np

from ruamel.yaml import YAML

#Rich stuff
from rich import print
from rich.console import Console
console = Console()
from rich.markdown import Markdown
from rich.traceback import install
install(show_locals=False)
from rich import inspect
from rich.padding import Padding


from freemocap import (
    recordingconfig,
    runcams,
    calibrate,
    fmc_mediapipe,
    fmc_openpose,
    fmc_deeplabcut,
    reconstruct3D,
    play_skeleton_animation,
    session,
)



thisStage = 0 #global

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
        showAnimation = True,
        reconstructionConfidenceThreshold = .7,
        charucoSquareSize = 36,#mm - ~the size of the squares when printed on 8.5x11" paper based on parameters in ReadMe.md
        calVideoFrameLength = -1,
        startFrame = 0,
        useBlender = False,
        resetBlenderExe = False,
        pauseBetweenStages =1
        ):
    """ 
    Starts the freemocap pipeline based on either user-input values, or default values. Creates a new session class instance (called sesh)
    based on the specified inputs. Checks for previous user preferences and choices if they exist, or will prompt the user for new choices
    if they don't. Runs the initialization for the system and runs each stage of the pipeline.
    """ 
    
    welcome_md = Markdown("""# Welcome to FreeMoCap ✨💀✨ """)
    console.print(welcome_md)
    
    sesh = session.Session()

    sesh.sessionID = sessionID
    sesh.useOpenPose= useOpenPose
    sesh.useMediaPipe = useMediaPipe
    sesh.useDLC= useDLC
    sesh.debug = debug
    sesh.setDataPath = setDataPath
    sesh.userDataPath = userDataPath
    sesh.dataFolderName = recordingconfig.dataFolder
    sesh.startFrame = startFrame

    # %% Startup 
    startup.get_user_preferences(sesh,stage)

    if sesh.useDLC and stage<5:
         import deeplabcut as dlc
         dlc_config_paths = startup.get_dlc_paths(session)

    if stage > 1:
        startup.get_data_folder_path(sesh)
    
        if sesh.sessionID == None:    
            subfolders = [f.path for f in os.scandir(sesh.dataFolderPath) if f.is_dir()]  # copy-pasta from who knows where
            sesh.sessionID = Path(subfolders[-1]).stem  # grab the name of the last folder in the list of subfolders
        
        console.rule()
        print('Running ' + str(sesh.sessionID) + ' from ' + str(sesh.dataFolderPath))
        console.rule()
    if useBlender == True:
        here = Path(__file__).parent
        subprocessPath = here/'fmc_blender.py'
        blenderEXEpath = startup.get_blender_path(sesh,resetBlenderExe)

 
    board = CharucoBoard(7, 5,
                        #square_length=1, # here, in mm but any unit works (JSM NOTE - just using '1' so resulting units will be in 'charuco squarelenghts`)
                        #marker_length=.8,
                        #  square_length = 121, #big boi charuco
                        #  marker_length = 98,
                        square_length = charucoSquareSize,#mm
                        marker_length = charucoSquareSize*.8,#mm
                        marker_bits=4, dict_size=250)
    sesh.board = board

   

    # %% Initialization
    if stage == 1:
        camera_settings.initialize(sesh,stage,board)
    elif stage ==2:
        timesync.time_sync_initialize(sesh)
    else:
        sesh.initialize(stage)

    # %% Stage One
    
    if stage <= 1:
        thisStage=1
        console.rule(style="color({})".format(thisStage))    
        console.rule('Starting Video Recordings'.upper(), style="color({})".format(thisStage))   
        console.rule(style="color({})".format(thisStage))    

        runcams.RecordCams(sesh, sesh.cam_inputs, sesh.parameterDictionary, sesh.rotationInputs)
        sesh.save_session()
    else:
        print('Skipping Video Recording')


    # %% Stage Two
    if stage <= 2:
        thisStage=2
        console.rule(style="color({})".format(thisStage))        
        console.rule('Synchronizing Recorded Videos'.upper(),style="color({})".format(thisStage))    
        console.rule(style="color({})".format(thisStage))    
        time.sleep(pauseBetweenStages)  
        runcams.SyncCams(sesh, sesh.timeStampData,sesh.numCamRange,sesh.vidNames,sesh.camIDs)
        sesh.save_session()
    else:
        print('Skipping Video Syncing')

    # %% Stage Three
    if stage <= 3:
        thisStage=3
        console.rule(style="color({})".format(thisStage))    
        console.rule('Starting Capture Volume Calibration'.upper(),style="color({})".format(thisStage))    
        console.rule(style="color({})".format(thisStage))  
        console.print(Padding('Using Anipose to calculate 6 degree-of-freedom position (and distortion coeffs) of each camera based on detected charuco boards. This information is used to create a Camera Projection Matrix for each camera, which is later used in the 3d reconstruction stage', (1,4)), overflow="fold", justify='center')
        console.rule('See https://anipose.org for details', style="color({})".format(thisStage))  
        console.rule(style="color({})".format(thisStage))    

        sesh.cgroup, sesh.mean_charuco_fr_mar_xyz = calibrate.CalibrateCaptureVolume(sesh,board, calVideoFrameLength, spoof_anipose_fail_bool=False)
        print('Anipose Calibration Successful!')
    else:
        print('Skipping Calibration')

    # %% Stage Four
    if stage <= 4:
        thisStage=4
        console.rule(style="color({})".format(thisStage))    
        console.rule('Starting 2D Point Trackers'.upper(),style="color({})".format(thisStage))    
        console.rule('This step impolements the machine learning driven computer vision convolutional neural networks that track the skeleton, etc', style="color({})".format(thisStage))    
        console.rule('This part is crazy future tech sci fi stuff. Seriously unbelievable this kind of thing is possible.', style="color({})".format(thisStage))    
        console.rule(style="color({})".format(thisStage))      
        time.sleep(pauseBetweenStages)  

        if sesh.useMediaPipe:
            console.rule(style="color({})".format(thisStage))    
            console.rule('Running MediaPipe skeleton tracker - https://google.github.io/mediapipe', style="color({})".format(thisStage))    
            console.rule(style="color({})".format(thisStage))    
            time.sleep(pauseBetweenStages)  

            if runMediaPipe:
                fmc_mediapipe.runMediaPipe(sesh)

            sesh.mediaPipeData_nCams_nFrames_nImgPts_XYC = fmc_mediapipe.parseMediaPipe(sesh)
            sesh.mediaPipeSkel_fr_mar_xyz, sesh.mediaPipeSkel_reprojErr = reconstruct3D.reconstruct3D(sesh,sesh.mediaPipeData_nCams_nFrames_nImgPts_XYC, confidenceThreshold=reconstructionConfidenceThreshold)
            np.save(sesh.dataArrayPath/'mediaPipeSkel_3d.npy', sesh.mediaPipeSkel_fr_mar_xyz) #save data to npy
            np.save(sesh.dataArrayPath/'mediaPipeSkel_reprojErr.npy', sesh.mediaPipeSkel_reprojErr) #save data to npy            
        sesh.save_session()

        if sesh.useOpenPose:
            console.rule(style="color({})".format(thisStage))    
            console.rule('Running OpenPose skeleton tracker - https://github.com/CMU-Perceptual-Computing-Lab/openpose', style="color({})".format(thisStage))    
            console.rule(style="color({})".format(thisStage))
            time.sleep(pauseBetweenStages)      

            fmc_openpose.runOpenPose(sesh, runOpenPose=runOpenPose)
            sesh.openPoseData_nCams_nFrames_nImgPts_XYC = fmc_openpose.parseOpenPose(sesh)
            sesh.openPoseSkel_fr_mar_xyz, sesh.openPoseSkel_reprojErr = reconstruct3D.reconstruct3D(sesh,sesh.openPoseData_nCams_nFrames_nImgPts_XYC, confidenceThreshold=reconstructionConfidenceThreshold)
            np.save(sesh.dataArrayPath/'openPoseSkel_3d.npy', sesh.openPoseSkel_fr_mar_xyz) #save data to npy
            np.save(sesh.dataArrayPath/'openPoseSkel_reprojErr.npy', sesh.openPoseSkel_reprojErr) #save data to npy
        sesh.save_session()
        sesh.syncedVidList = []

        if sesh.useDLC:
            
            console.rule(style="color({})".format(thisStage))    
            console.rule('Running DeepLabCut :mouse: - https://deeplabcut.org', style="color({})".format(thisStage))    
            console.rule(style="color({})".format(thisStage)) 
            time.sleep(pauseBetweenStages)     

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
        print('Skipping 2d point tracking')



    if stage <=5:
        if useBlender == True:
            thisStage=5
            console.rule(style="color({})".format(thisStage))    
            console.rule('Exporting Files...'.upper(), style="color({})".format(thisStage))    
            console.rule('Hijacking Blender\'s file format converters to export FreeMoCap data as various file format (.blend, .usd, .gltf, .fbx)', style="color({})".format(thisStage))    
            console.rule(style="color({})".format(thisStage))    
            time.sleep(pauseBetweenStages)  

            #blenderExePath = Path('C:\Program Files\Blender Foundation\Blender 2.93')
            #os.chdir(blenderExePath)
            output = subprocess.run([blenderEXEpath, "--background", "--python", str(subprocessPath), "--", str(sesh.dataArrayPath/'mediaPipeSkel_3d.npy')], capture_output=True, text=True, check=True)
            print(output)        

    # %% Stage Five - Make Skreleton Animation
    if stage <= 6:
        thisStage=6
        console.rule(style="color({})".format(thisStage))    
        console.rule('Creating the Skelton animation!'.upper(),style="color({})".format(thisStage))    
        console.rule('The video creation is very slow. This whole animation maker is crazy slow, tbh. Sorry about that :sweat_smile:',style="color({})".format(thisStage))    
        console.rule(style="color({})".format(thisStage))    
        time.sleep(pauseBetweenStages)  
        
        play_skeleton_animation.PlaySkeletonAnimation(
                                sesh,
                                startFrame=sesh.startFrame,
                                azimuth=-90,
                                elevation=-81,
                                useOpenPose=useOpenPose,
                                useMediaPipe=useMediaPipe,
                                useDLC=useDLC,
                                recordVid = recordVid,
                                showAnimation=showAnimation,
                                )
        console.rule(style="color({})".format(thisStage))    
    else:
        print('Skipping Skeleton Plotting')


    console.rule(style="color({})".format(13))      
    console.rule('All Done!'.upper(), style="color({})".format(13))    
    console.rule(style="color({})".format(13))    
    console.rule('Session Data folder is at: ', style="color({})".format(13))    
    console.rule(str(sesh.sessionPath), style="color({})".format(13))    
    console.rule(style="color({})".format(13))    
    console.rule("Thank you for supporting the FreeMoCap Project", style="color({})".format(13))    
    console.rule(style="color({})".format(13))    
    console.rule(style="color({})".format(13))    
    console.rule('~✨💀✨~',style="color({})".format(0)) 
    time.sleep(.1) #Maybe helps so that rich doesn't print a newline after a rule with an emoji?
    console.rule('❤️',style="color({})".format(0)) 
    console.rule(style="color({})".format(13))    
    console.rule(style="color({})".format(13))    

