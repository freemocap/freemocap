
from freemocap.fmc_startup import startup, startupGUI
from freemocap.webcam import camera_settings, timesync

from pathlib import Path
import os
import subprocess
import time 
from aniposelib.boards import CharucoBoard

import numpy as np
from scipy.signal import savgol_filter

import cv2

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

# TODO: Replace the below functions with the RunMe options.
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
        reconstructionConfidenceThreshold = .5,
        charucoSquareSize = 36,#mm - ~the size of the squares when printed on 8.5x11" paper based on parameters in ReadMe.md
        calVideoFrameLength = 1,
        startFrame = 0,
        useBlender = False,
        resetBlenderExe = False,
        get_synced_unix_timestamps = True,
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
    sesh.get_synced_unix_timestamps = get_synced_unix_timestamps

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
        blenderPath = startup.get_blender_path(sesh,resetBlenderExe)


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
        console.rule(style="color({})".format(14))
        console.rule('Starting Video Recordings'.upper(), style="color({})".format(14))
        console.rule(style="color({})".format(14))

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
        console.print(Padding('Using Anipose to calculate 6 degree-of-freedom position (and distortion coeffs) of each camera based on detected charuco boards. This information is used to create a Camera Projection Matrix for each camera, which is later used in the 3d reconstruction stage', (1,4)), overflow="fold", justify='center',style="color({})".format(thisStage))
        console.rule('See https://anipose.org for details', style="color({})".format(thisStage))
        console.rule(style="color({})".format(thisStage))

        if sesh.numFrames is None:
            a_sync_vid_path = list(sesh.syncedVidPath.glob('*.mp4'))
            temp_cap =   cv2.VideoCapture(str(a_sync_vid_path[0]))
            sesh.numFrames = temp_cap.get(cv2.CAP_PROP_FRAME_COUNT)
            temp_cap.release()

        sesh.cgroup, sesh.mean_charuco_fr_mar_xyz = calibrate.CalibrateCaptureVolume(sesh,board, calVideoFrameLength)

        ##this is supposed to cycle through tyhe videos with different windows to try to get Anipose to work. I can't get the dang thing working because something weird happens where a Thread will get spawned in one of the inner functions (maybe related to tqdm?) and that iteration will jump out of the try/except
        # try:
        #     sesh.cgroup, sesh.mean_charuco_fr_mar_xyz = calibrate.CalibrateCaptureVolume(sesh,board, calVideoFrameLength)
        #     # anipose_success = True
        #     anipose_success = False
        # except:
        #     console.print_exception()
        #     console.print('[bold red] - Anipose Calibration failed with user-provided (or default) `calVideoFrameLength` value! Trying again with other parts of the videos')
        #     anipose_success = False

        # if not anipose_success:
        #     if calVideoFrameLength ==.25:
        #         cal_video_frame_range = [round(sesh.numFrames*.25), round(sesh.numFrames*.5)]
        #     else:
        #         cal_video_frame_range = [0, round(sesh.numFrames*.25)]

        #     for anipose_iter in range(4):

        #         console.rule('Anipose Failed - Reprocessing - Iteration #{}'.format(anipose_iter), style="color({})".format(thisStage))
        #         console.rule('Trying again with frame range {} - {}'.format(cal_video_frame_range[0], cal_video_frame_range[1]), style="color({})".format(thisStage))

        #         try:
        #             sesh.cgroup, sesh.mean_charuco_fr_mar_xyz = calibrate.CalibrateCaptureVolume(sesh,board, cal_video_frame_range)
        #             break
        #         except:
        #             console.print_exception()
        #             cal_video_frame_range = [cal_video_frame_range[0]+round(sesh.numFrames*.25), cal_video_frame_range[0]+round(sesh.numFrames*.5)]

        #         if cal_video_frame_range[1] > sesh.numFrames:
        #             console.print('[bold red] -Sorry, we couldn\'t get Anipose calibration to complete sucessfully. Are you using a Charuco board made with the parameters described in the ReadMe (here\s a sample png -https://github.com/jonmatthis/freemocap/blob/main/charuco_board_image.png ). Is the board clearly visible to each camera? Is there glare on it from from any of the camera\'s perspective? Is it too far away from the cameras? Is your `exposure` set low enough that the black squares are black (not grey)?')




        print('Anipose Calibration Successful!')
    else:
        print('Skipping Calibration')

    # %% Stage Four
    if stage <= 4:
        thisStage=4
        thisStageColor=12
        console.rule(style="color({})".format(thisStageColor))
        console.rule('Starting 2D Point Trackers'.upper(),style="color({})".format(thisStageColor))
        stage4_msg ='This step implements various  computer vision that track the skeleton (and other objects) in the 2d videos, to produce the data that will be combined with the `camera projection matrices` from the calibration stage to produce the estimates of 3d movement. \n \n Each algorithm is different, but most involve using [bold magenta] convolutional neural networks [/bold magenta] trained from labeled videos to produce a 2d probability map of the likelihood that the tracked bodypart/object/feature (e.g. \'LeftElbow\') is in a given location. \n \n The peak of that distrubtion on each frame is recorded as the pixel-location of that item on that frame (e.g. \'LeftElbow(pixel-x, pixel-y, confidence\') where the a confidence value proportional to the underlying probability distribution (i.e. tall peaks in the probablitiy distribution indicate high confidence that the LeftElbow actually is at this pixel-x, pixel-y location) \n \nThis part is crazy future tech sci fi stuff. Seriously unbelievable this kind of thing is possible ✨'
        console.print(Padding(stage4_msg, (1,4)), overflow="fold", justify='center',style="color({})".format(thisStageColor))
        console.rule(style="color({})".format(thisStageColor))


        if sesh.useMediaPipe:
            console.rule(style="color({})".format(thisStage))
            console.rule('Running MediaPipe skeleton tracker - https://google.github.io/mediapipe', style="color({})".format(thisStage))
            console.rule(style="color({})".format(thisStage))


            if runMediaPipe:
                fmc_mediapipe.runMediaPipe(sesh)
                sesh.mediaPipeData_nCams_nFrames_nImgPts_XYC = fmc_mediapipe.parseMediaPipe(sesh)




            else:
                print('`runMediaPipe` set to False, so we\'re loading MediaPipe data from npy file')
                sesh.mediaPipeData_nCams_nFrames_nImgPts_XYC = np.load(sesh.dataArrayPath/'mediaPipeData_2d.npy', allow_pickle=True)

            sesh.mediaPipeSkel_fr_mar_xyz, sesh.mediaPipeSkel_reprojErr = reconstruct3D.reconstruct3D(sesh,sesh.mediaPipeData_nCams_nFrames_nImgPts_XYC, confidenceThreshold=reconstructionConfidenceThreshold)

            np.save(sesh.dataArrayPath/'mediaPipeSkel_3d.npy', sesh.mediaPipeSkel_fr_mar_xyz) #save data to npy
            np.save(sesh.dataArrayPath/'mediaPipeSkel_reprojErr.npy', sesh.mediaPipeSkel_reprojErr) #save data to npy

            #smoooooooooth, just a bit
            smoothWinLength = 5
            smoothOrder = 3
            for dim in range(sesh.mediaPipeSkel_fr_mar_xyz.shape[2]):
                for mm in range(sesh.mediaPipeSkel_fr_mar_xyz.shape[1]):
                    sesh.mediaPipeSkel_fr_mar_xyz[:,mm,dim] = savgol_filter(sesh.mediaPipeSkel_fr_mar_xyz[:,mm,dim], smoothWinLength, smoothOrder)

            np.save(sesh.dataArrayPath/'mediaPipeSkel_3d_smoothed.npy', sesh.mediaPipeSkel_fr_mar_xyz) #save data to npy

        sesh.save_session()


        if sesh.useOpenPose:
            console.rule(style="color({})".format(thisStage))
            console.rule('Running OpenPose skeleton tracker - https://github.com/CMU-Perceptual-Computing-Lab/openpose', style="color({})".format(thisStage))
            console.rule(style="color({})".format(thisStage))


            fmc_openpose.runOpenPose(sesh, runOpenPose=runOpenPose)
            sesh.openPoseData_nCams_nFrames_nImgPts_XYC = fmc_openpose.parseOpenPose(sesh)
            sesh.openPoseSkel_fr_mar_xyz, sesh.openPoseSkel_reprojErr = reconstruct3D.reconstruct3D(sesh,sesh.openPoseData_nCams_nFrames_nImgPts_XYC, confidenceThreshold=reconstructionConfidenceThreshold)
            np.save(sesh.dataArrayPath/'openPoseSkel_3d.npy', sesh.openPoseSkel_fr_mar_xyz) #save data to npy
            np.save(sesh.dataArrayPath/'openPoseSkel_reprojErr.npy', sesh.openPoseSkel_reprojErr) #save data to npy

            smoothWinLength = 5
            smoothOrder = 3
            for dim in range(sesh.openPoseSkel_fr_mar_xyz.shape[2]):
                for mm in range(sesh.openPoseSkel_fr_mar_xyz.shape[1]):
                    sesh.openPoseSkel_fr_mar_xyz[:,mm,dim] = savgol_filter(sesh.openPoseSkel_fr_mar_xyz[:,mm,dim], smoothWinLength, smoothOrder)

            np.save(sesh.dataArrayPath/'openPoseSkel_3d_smoothed.npy', sesh.openPoseSkel_fr_mar_xyz) #save data to npy

        sesh.save_session()
        sesh.syncedVidList = []

        if sesh.useDLC:

            console.rule(style="color({})".format(thisStage))
            console.rule('Running DeepLabCut :mouse: - https://deeplabcut.org', style="color({})".format(thisStage))
            console.rule(style="color({})".format(thisStage))


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


    # %% Stage 5 - Use Blender to create output data files
    if stage <=5:
        try:
            if useBlender == True:
                thisStage=5
                console.rule(style="color({})".format(thisStage))
                console.rule('Exporting Files...'.upper(), style="color({})".format(thisStage))
                console.rule('Hijacking Blender\'s file format converters to export FreeMoCap data as various file format (.blend, .usd, .gltf, .fbx)', style="color({})".format(thisStage))
                console.rule(style="color({})".format(thisStage))

                path_to_this_py_file = Path(__file__).parent.resolve()
                fmc_blender_script_path = path_to_this_py_file /'freemocap_blender_megascript.py'
 
                command_str = str(blenderPath) + " --background" + " --python " +  str(fmc_blender_script_path) +  " -- " +  str(sesh.sessionPath)
                # command_str = [str(blenderPath), "--background", "--python", str(fmc_blender_script_path), "--", str(sesh.sessionPath)]
                blender_process = subprocess.Popen(
                                        command_str,
                                        shell=False,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE
                                        )
                while True:
                    output = blender_process.stdout.readline()
                    if blender_process.poll() is not None:
                        break
                    if output:
                        print(output.strip().decode())


        except:
            console.print_exception()


    # %% Stage 6 - Make  Animation
    if stage <= 6:
        thisStage=6
        console.rule(style="color({})".format(thisStage))
        console.rule('Creating the Skreleton animation!'.upper(),style="color({})".format(thisStage))
        console.print('The video creation is very slow. All of the animation making code is crazy slow, tbh. Sorry about that, future iterations will be better lol :sweat_smile:',overflow="fold", justify='center',style="color({})".format(thisStage))
        console.rule(style="color({})".format(thisStage))



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
    console.rule(style="color({})".format(10))
    console.rule("Thank you for supporting the FreeMoCap Project", style="color({})".format(10))
    console.rule(style="color({})".format(10))
    console.rule(style="color({})".format(13))
    console.print('~✨💀✨~',justify="center")
    console.print('❤️', justify="center")
    console.rule(style="color({})".format(13))
    console.rule(style="color({})".format(14))
