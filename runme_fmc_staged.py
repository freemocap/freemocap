from freemocap import createvideo, initialization, recordingconfig, runcams, calibrate, fmc_mediapipe, fmc_openpose, fmc_deeplabcut, reconstruct3D, playskeleton, session
from freemocap.fmc_pyqtgraph import PlayerDockedWindow

from pathlib import Path
import os

from aniposelib.boards import CharucoBoard

import numpy as np

sesh = session.Session()


sesh.useOpenPose= True
sesh.useMediaPipe = True
sesh.useDLC=False

if sesh.useDLC: 
    import deeplabcut as dlc
    sesh.dlcConfigPath = Path("C:\\Users\\jonma\\Dropbox\\GitKrakenRepos\\freemocap\\DLC_Models\\PinkGreenRedJugglingBalls-JSM-2021-05-31\\config.yaml")



# %% Inputs to edit
stage = 7 #set your starting stage here (stage = 1 will run the pipeline from webcams)
sesh.debug = False

sesh.sessionID = 'sesh_21-06-10_151714' #fill in if you are running from Stage 2 onwards
if not sesh.sessionID:
    dataFolder = Path.cwd()/'Data'
    subfolders = [ f.path for f in os.scandir(dataFolder) if f.is_dir() ] #copy-pasta from who knows where
    sesh.sessionID = Path(subfolders[-1]).stem #grab the name of the last folder in the list of subfolders



board = CharucoBoard(7, 5,
                     #square_length=1, # here, in mm but any unit works (JSM NOTE - just using '1' so resulting units will be in 'charuco squarelenghts`)
                     #marker_length=.8,
                    #  square_length = 121, #big boi charuco
                    #  marker_length = 98,
                     square_length = 82,#regular boi charuco
                     marker_length = 65,
                     marker_bits=4, dict_size=250)



#sesh.input_stage = stage



# %% Initialization

initialization.initialize(sesh,stage,board)

# %% Stage One
if stage <= 1:
    print()
    print('Starting Video Recordings')
    runcams.RecordCams(sesh, sesh.cam_inputs, sesh.parameterDictionary, sesh.rotationInputs)
else:
    print('Skipping Video Recording')


# %% Stage Two
if stage <= 2:
    print()
    print('Starting Video Syncing')
    runcams.SyncCams(sesh, sesh.timeStampData,sesh.numCamRange,sesh.vidNames,sesh.camIDs)
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
sesh.config_settings = recordingconfig.load_config_yaml(sesh.yamlPath)

# %% Stage Seven
if stage <= 7:
    print('Starting Skeleton Plotting')
    # playskeleton.ReplaySkeleton_matplotlib(
    #                             sesh,
    #                             vidType=1,
    #                             startFrame=40,
    #                             azimuth=-90, 
    #                             elevation=-80,
    #                             useOpenPose=useOpenPose,
    #                             useMediaPipe=useMediaPipe,
    #                             useDLC=useDLC)
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
    playWin =PlayerDockedWindow(sesh)
    playWin.animate()

else:
    print('Skipping Skeleton Plotting')
    
# %% Stage Eight
if stage <= 8:
    print()
    print('Starting Video Creation')
    createvideo.createVideo(sesh)
else:
    print('Skipping Video Creation')
    


f = 9