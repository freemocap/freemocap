from freemocap import createvideo, initialization, runcams, calibrate, fmc_openpose, reconstruct3D, playskeleton, session

from pathlib import Path
import os

from aniposelib.boards import CharucoBoard, Checkerboard

import numpy as np



sesh = session.Session(useOpenPose=True,useDLC=False)

# %% Inputs to edit
stage = 1 #set your starting stage here (stage = 1 will run the pipeline from webcams)
sesh.debug = False
sesh.sessionID = '' #fill in if you are running from Stage 2 onwards 

sesh.sessionID = '' #fill in if you are running from Stage 2 onwards
if not sesh.sessionID:
    dataFolder = Path.cwd()/'Data'
    subfolders = [ f.path for f in os.scandir(dataFolder) if f.is_dir() ] #copy-pasta from who knows where
    sesh.sessionID = Path(subfolders[-1]).stem #grab the name of the last folder in the list of subfolders
=======
stage = 1 #set your starting stage here (stage = 1 will run the pipeline from webcams)
sesh.debug = True
sesh.sessionID = '' #fill in if you are running from Stage 2 onwards 
>>>>>>> 8f1fbc8... runme file reorganization

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
    runcams.RecordCams(sesh, sesh.cam_inputs, sesh.parameterDictionary, sesh.rotationInputs)
else:
    print('Skipping Video Recording')


# %% Stage Two
if stage <= 2:
    runcams.SyncCams(sesh, sesh.timeStampData,sesh.numCamRange,sesh.vidNames,sesh.camIDs)
else:
    print('Skipping Video Syncing')

# %% Stage Three
if stage <= 3:
    sesh.cgroup, sesh.mean_charuco_fr_mar_dim = calibrate.CalibrateCaptureVolume(sesh,board)
else:
    print('Skipping Calibration')

# %% Stage Four
if stage <= 4:
    fmc_openpose.runOpenPose(sesh)
else:
    print('Skipping Running OpenPose')

# %% Stage Five
if stage <= 5:
    sesh.openPoseData_nCams_nFrames_nImgPts_XY = fmc_openpose.parseOpenPose(sesh)
else:
    print('Skipping Parse OpenPose')


#  #%% process DLC
 
#  deeplabcut.analyze_videos(sesh.dlcConfigPath,sesh.sessionPath/'SyncedVideos', destfolder= sesh.dlcDataPath)    
    
# %% Stage Six
if stage <= 6:
    openPose_params = sesh.openPoseData_nCams_nFrames_nImgPts_XY.shape[0:3]
    sesh.skel_fr_mar_dim = reconstruct3D.reconstruct3D(sesh,sesh.openPoseData_nCams_nFrames_nImgPts_XY, openPose_params)

    path_to_skel_points = sesh.dataArrayPath/'skeleton_points.npy'
    np.save(path_to_skel_points, sesh.skel_fr_mar_dim)
else:
    print('Skipping Skeleton Reconstruction')
  
# %% Stage Seven
if stage <= 7:
    playskeleton.ReplaySkeleton(sesh,1,40,-90,-75)
else:
    print('Skipping Skeleton Plotting')
    
# %% Stage Eight
if stage <= 8:
    createvideo.createVideo(sesh)
else:
    print('Skipping Video Creation')
    


f = 9