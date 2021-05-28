from freemocap import createvideo, initialization, runcams, calibrate, runopenpose, reconstruct3D, playskeleton, session


from aniposelib.boards import CharucoBoard, Checkerboard

import numpy as np


# %% Inputs to edit

stage = 8 #set your starting stage here (stage = 1 will run the pipeline from webcams)

board = CharucoBoard(7, 5,
                     #square_length=1, # here, in mm but any unit works (JSM NOTE - just using '1' so resulting units will be in 'charuco squarelenghts`)
                     #marker_length=.8,
                     square_length = 7,
                     marker_length = 6.8,
                     marker_bits=4, dict_size=250)


sesh = session.Session(useOpenPose=True,useDLC=False)
sesh.input_stage = stage
sesh.debug = True
sesh.sessionID = 'sesh_21-05-28_113930' #fill in if you are running from Stage 2 onwards


# %% Initialization

initialization.initialize(sesh,stage,board)

# %% Stage One
if not stage > 1:
    runcams.RecordCams(sesh, sesh.cam_inputs, sesh.parameterDictionary, sesh.rotationInputs)
else:
    print('Skipping Video Recording')


# %% Stage Two
if not stage > 2:
    runcams.SyncCams(sesh, sesh.timeStampData,sesh.numCamRange,sesh.vidNames,sesh.camIDs)
else:
    print('Skipping Video Syncing')

if not stage > 3:
    sesh.cgroup, sesh.mean_charuco_fr_mar_dim = calibrate.CalibrateCaptureVolume(sesh,board)
else:
    print('Skipping Calibration')

if not stage > 4:
    runopenpose.runOpenPose(sesh)
else:
    print('Skipping Running OpenPose')

if not stage > 5:
    sesh.openPoseData_nCams_nFrames_nImgPts_XY = runopenpose.parseOpenPose(sesh)
else:
    print('Skipping Parse OpenPose')
    


if not stage > 6:
    openPose_params = sesh.openPoseData_nCams_nFrames_nImgPts_XY.shape[0:3]
    sesh.skel_fr_mar_dim = reconstruct3D.reconstruct3D(sesh,sesh.openPoseData_nCams_nFrames_nImgPts_XY, openPose_params)

    path_to_skel_points = sesh.dataArrayPath/'skeleton_points.npy'
    np.save(path_to_skel_points, sesh.skel_fr_mar_dim)
else:
    print('Skipping Skeleton Reconstruction')
 

if not stage > 7:
    playskeleton.ReplaySkeleton(sesh,1,40,-90,-75)
else:
    print('Skipping Skeleton Plotting')
    

if not stage > 8:
    createvideo.createVideo(sesh)
else:
    print('Skipping Video Creation')
    


f = 2