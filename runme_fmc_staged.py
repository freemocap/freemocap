from freemocap import createvideo, initialization, runcams, calibrate, runmediapipe, reconstruct3D, playskeleton, session

from pathlib import Path
import os

from aniposelib.boards import CharucoBoard, Checkerboard

import numpy as np



sesh = session.Session(useOpenPose=True,useDLC=False)

# %% Inputs to edit
stage = 1 #set your starting stage here (stage = 1 will run the pipeline from webcams)
sesh.debug = True

sesh.sessionID = '' #fill in if you are running from Stage 2 onwards
if not sesh.sessionID:
    dataFolder = Path.cwd()/'Data'
    subfolders = [ f.path for f in os.scandir(dataFolder) if f.is_dir() ] #copy-pasta from who knows where
    sesh.sessionID = Path(subfolders[-1]).stem #grab the name of the last folder in the list of subfolders

board = CharucoBoard(7, 5,
                     #square_length=1, # here, in mm but any unit works (JSM NOTE - just using '1' so resulting units will be in 'charuco squarelenghts`)
                     #marker_length=.8,
                     square_length = 7,
                     marker_length = 6.8,
                     marker_bits=4, dict_size=250)



#sesh.input_stage = stage



# %% Initialization

initialization.initialize(sesh,stage,board)

# %% Stage One
if not stage > 1:
    print()
    print('Starting Video Recordings')
    runcams.RecordCams(sesh, sesh.cam_inputs, sesh.parameterDictionary, sesh.rotationInputs)
else:
    print('Skipping Video Recording')


# %% Stage Two
if not stage > 2:
    print()
    print('Starting Video Syncing')
    runcams.SyncCams(sesh, sesh.timeStampData,sesh.numCamRange,sesh.vidNames,sesh.camIDs)
else:
    print('Skipping Video Syncing')

# %% Stage Three
if not stage > 3:
    print()
    print('Starting Calibration')
    sesh.cgroup, sesh.mean_charuco_fr_mar_dim = calibrate.CalibrateCaptureVolume(sesh,board)
else:
    print('Skipping Calibration')

# %% Stage Four
if not stage > 4:
    print()
    print('Starting Run MediaPipe')
    runmediapipe.runMediaPipe(sesh)
else:
    print('Skipping Run MediaPipe')

# %% Stage Five
if not stage > 5:
    print()
    print('Starting Parse MediaPipe')
    sesh.mediaPipeData_nCams_nFrames_nImgPts_XY = runmediapipe.parseMediaPipe(sesh)
else:
    print('Skipping Parse MediaPipe')
    
# %% Stage Six
if not stage > 6:
    print()
    print('Starting Skeleton Reconstruction')
    mediaPipe_params = sesh.mediaPipeData_nCams_nFrames_nImgPts_XY.shape[0:3]
    sesh.skel_fr_mar_dim = reconstruct3D.reconstruct3D(sesh,sesh.mediaPipeData_nCams_nFrames_nImgPts_XY, mediaPipe_params)

    path_to_skel_points = sesh.dataArrayPath/'skeleton_points.npy'
    np.save(path_to_skel_points, sesh.skel_fr_mar_dim)
else:
    print('Skipping Skeleton Reconstruction')
 
# %% Stage Seven
if not stage > 7:
    print()
    print('Starting Skeleton Plotting')
    playskeleton.ReplaySkeleton(sesh,1,40,-90,-75)
else:
    print('Skipping Skeleton Plotting')
    
# %% Stage Eight
if not stage > 8:
    print()
    print('Starting Video Creation')
    createvideo.createVideo(sesh)
else:
    print('Skipping Video Creation')
    


f = 2