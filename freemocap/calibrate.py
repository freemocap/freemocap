from aniposelib.cameras import CameraGroup
from aniposelib.utils import load_pose2d_fnames
import numpy as np
import cv2

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from freemocap import reconstruct3D, fmc_anipose
import os
from rich.progress import track



def CalibrateCaptureVolume(session,board, calVideoFrameLength = 120):
    """ 
    Check if a previous calibration yaml exists, and if not, create a set of shortened calibration videos and run Anipose functions
    to create a calibration yaml. Takes the 2D charuco board points and reconstructs them into 3D points that are saved out
    into the DataArrays folder
    """  
    session.calVidPath.mkdir(exist_ok = True)
    session.dataArrayPath.mkdir(exist_ok = True)

    if calVideoFrameLength < 0:
        calVideoFrameLength = session.numFrames
        calibrationVideoPath = session.syncedVidPath
    else:    
        createCalibrationVideos(session, calVideoFrameLength)
        calibrationVideoPath = session.calVidPath

    vidnames = []
    cam_names = []
    for count, thisVidPath in enumerate(calibrationVideoPath.glob("*.mp4"), start=1):
        vidnames.append([str(thisVidPath)])
        cam_names.append(str(count))
        session.numCams = count

    cgroup = fmc_anipose.CameraGroup.from_names(
        cam_names, fisheye=True
    )  # Looking through their code... it looks lke the 'fisheye=True' doesn't do much (see 2020-03-29 obsidian note)

    calibrationFile = "{}_calibration.yaml".format(session.sessionID)

    session.cameraCalFilePath = session.sessionPath / calibrationFile

    forceRunCameraExtrinsicsCalibration = True  # set this to True to re-run the camera calibration and saveover the existing config file

    # if not session.cameraCalFilePath.exists() or forceRunCameraExtrinsicsCalibration: #if that config file doesn't exist, run the camera calibration whosists. If it does, then just load the toml
    ## this will take a few minutes
    ## it will detect the charuco board in the videos,
    ## then calibrate the cameras based on the detections, using iterative bundle adjustment
    # error,all_rows,merged = cgroup.calibrate_videos(vidnames, board) #JSM NOTE - in its original form, this method doesn't throw an error when a video fails to load. This is an easy fix!

    #%% This next bit is a copy-paste of the inner bits of `cgroup.calibrate_videos` - Part 1 of 2
    """Takes as input a list of list of video filenames, one list of each camera.
    Also takes a board which specifies what should be detected in the videos"""

    error,charuco_data, charuco_frames = cgroup.calibrate_videos(vidnames, board)
    cgroup.dump(session.cameraCalFilePath) #JSM NOTE  - let's just use .yaml's unless there is some reason to use .toml



    session.cgroup = cgroup
    n_frames = calVideoFrameLength
    startframe = 0
    n_trackedPoints = 24
    framelist = range(startframe, startframe + n_frames)

    charuco_nCams_nFrames_nImgPts_XY = np.empty([session.numCams, n_frames, n_trackedPoints,  2])
    charuco_nCams_nFrames_nImgPts_XY[:] = np.nan

    for cam in range(session.numCams):
        for charCount, thisCharFrame in enumerate(charuco_frames):
            try:
                charuco_nCams_nFrames_nImgPts_XY[cam, thisCharFrame, :,:] = np.squeeze(charuco_data[charCount][cam]["filled"])
            except:
                # print("failed frame:", frame)
                continue
    
    charuco2d_filename = session.dataArrayPath/'charuco_2d_points.npy'
    np.save(charuco2d_filename,charuco_nCams_nFrames_nImgPts_XY)

    session.charuco_nCams_nFrames_nImgPts_XY = charuco_nCams_nFrames_nImgPts_XY

    charuco_fr_mar_dim = reconstruct3D.reconstruct3D(
        session, charuco_nCams_nFrames_nImgPts_XY
    )

    mean_charuco_fr_mar_dim = np.nanmean(charuco_fr_mar_dim, axis=0)

    # charry_reshaped = charucoarray.reshape(session.numCams, -1, 2)

    # char_flat = cgroup.triangulate(charry_reshaped, progress=True)
    # charReprojerr_flat = cgroup.reprojection_error(char_flat, charry_reshaped, mean=True)

    # char_fr_mar_dim = char_flat.reshape(n_frames, n_trackedPoints, 3)
    # charReprojErr_fr_mar_err = charReprojerr_flat.reshape(n_frames, n_trackedPoints)

    if session.debug:
        fig = plt.figure()
        # mean charuco position
        ax1 = fig.add_subplot(111, projection="3d")
        ax1.cla()
        x = mean_charuco_fr_mar_dim[:][:, 0]
        y = mean_charuco_fr_mar_dim[:][:, 1]
        z = mean_charuco_fr_mar_dim[:][:, 2]
        mx = np.nanmean(x)
        my = np.nanmean(y)
        mz = np.nanmean(z)

        ax1.scatter(x, y, z, marker="o")
        ax1.set_title("Mean Charuco Point Positions")

        ax1.set_xlabel("x")
        ax1.set_ylabel("y")
        ax1.set_zlabel("z")

        for camNum in range(len(cgroup.cameras)):
            np.append(mx, cgroup.cameras[camNum].tvec[0])
            np.append(my, cgroup.cameras[camNum].tvec[1])
            np.append(mz, cgroup.cameras[camNum].tvec[2])

            ax1.scatter(
                cgroup.cameras[camNum].tvec[0],
                cgroup.cameras[camNum].tvec[1],
                cgroup.cameras[camNum].tvec[2],
                marker="p",
            )

        axRange = board.square_length * 5

        ax1.set_xlim(mx - axRange, mx + axRange)
        ax1.set_ylim(my - axRange, my + axRange)
        ax1.set_zlim(mz - axRange, mz + axRange)

        # #charuco points over time
        # ax2 = fig.add_subplot(122)
        # ax2.cla()
        # numPts = charuco_fr_mar_dim.shape[1]
        # for pp in range(numPts):
        #     ax2.plot(charuco_fr_mar_dim[:,pp,:])
        # ax2.set_title('Charuco Point positions over time')
        plt.show()

    path_to_charuco_array = session.dataArrayPath/'charuco_3d_points.npy'
    np.save(path_to_charuco_array, charuco_fr_mar_dim)
    return cgroup, mean_charuco_fr_mar_dim


def createCalibrationVideos(session, calVideoFrameLength):
    """ 
    Based on the desired length of the calibration videos (for the anipose functions), create new videos trimmed 
    to that specific length
    """  
    vidList = os.listdir(session.syncedVidPath)
    framelist = list(range(calVideoFrameLength))
    codec = "DIVX"
    for count, vid in enumerate(vidList, start=1):
        cam_name = "Cam{}".format(count)
        cap = cv2.VideoCapture(str(session.syncedVidPath / vid))
        fourcc = cv2.VideoWriter_fourcc(*codec)

        # grab resolution parameters from the videos
        resWidth = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        resHeight = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        framerate = int(cap.get(cv2.CAP_PROP_FPS))

        saveName = (
            session.sessionID + "_trimmed_" + cam_name + ".mp4"
        )  # create a name for the trimmed video
        saveCalVidPath = str(
            session.calVidPath / saveName
        )  # create an output path for the function

        success, image = cap.read()  # start reading frames

        out = cv2.VideoWriter(saveCalVidPath, fourcc, framerate, (resWidth, resHeight))
        print("Trimming " + cam_name)
        for frame in track(framelist):
            cap.set(
                cv2.CAP_PROP_POS_FRAMES, frame
            )  # set the video to the frame that we need
            success, image = cap.read()
            out.write(image)
        cap.release()
        out.release()
