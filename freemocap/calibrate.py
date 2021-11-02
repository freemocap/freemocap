import os
import copy

from aniposelib.cameras import CameraGroup
from aniposelib.utils import load_pose2d_fnames
from numba.core.types.misc import StringLiteral
import numpy as np
import cv2

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from freemocap import reconstruct3D, fmc_anipose
from rich.progress import track
from rich import print
from rich.console import Console
console = Console()


def CalibrateCaptureVolume(session,board, calVideoFrameLength = .25):
    """ 
    Check if a previous calibration yaml exists, and if not, create a set of shortened calibration videos and run Anipose functions
    to create a calibration yaml. Takes the 2D charuco board points and reconstructs them into 3D points that are saved out
    into the DataArrays folder

    note `debugAniposeIter` spoofs a failed anipose calibration to make it easier to test the thing where we iterate through with different frame windows to try to find one that works
    """  
    
    session.calVidPath.mkdir(exist_ok = True)
    session.dataArrayPath.mkdir(exist_ok = True)
    calibrationVideoPath = session.calVidPath

    if type(calVideoFrameLength)==int or type(calVideoFrameLength)==float:
        if calVideoFrameLength < 0: # if '-1' use the whole video
            calVideoFrameLength = [0, session.numFrames]
            calibrationVideoPath = session.calVidPath
        else:
            if calVideoFrameLength>0 and calVideoFrameLength<1: #if between 0 and 1, use as a percentage of the total video length
                calVideoFrameLength = [0, round(calVideoFrameLength * session.numFrames)]
            else: #otherwise, just use the input value as the number of frames to use        
                calVideoFrameLength = [0, calVideoFrameLength]

    createCalibrationVideos(session, calVideoFrameLength)



    vidnames = []
    cam_names = []
    for count, thisVidPath in enumerate(calibrationVideoPath.glob("*.mp4"), start=1):
        vidnames.append([str(thisVidPath)])
        cam_names.append(str(count))
        session.numCams = count

    cgroup = fmc_anipose.CameraGroup.from_names( cam_names, fisheye=True  )  # Looking through their code... it looks lke the 'fisheye=True' doesn't do much (see 2020-03-29 obsidian note)

    calibrationFile = "{}_calibration.yaml".format(session.sessionID)

    session.cameraCalFilePath = session.sessionPath / calibrationFile

    error,charuco_data, charuco_frames = cgroup.calibrate_videos(vidnames, board)
    
    ## iteratively retry if anipose fails, butcouldn't get this to work because anipose launches some weird thread process that doesn't terminate properly? 
    # try:
    #     error,charuco_data, charuco_frames = cgroup.calibrate_videos(vidnames, board)
    #     if not spoof_anipose_fail_bool:
    #         anipose_success = True        
    #     else:
    #         anipose_success = False
    # except:
    #     anipose_success = False
    #     console.rule('Anipose Calibration Failed for frame range {} - {}'.format(calVideoFrameLength[0], calVideoFrameLength[1]), style="color({})".format(3))

    # anipose_iter = -1
    # if not anipose_success: #%% run anipose calibration, and if it fails, re-make calibration vids with different frame range and try again
        
    #     frame_window_size = round(session.numFrames*.5)
    #     cal_video_frame_range = [0, frame_window_size]
    #     while not anipose_success:
    #             anipose_iter += 1
    #             console.rule('Anipose Failed - Reprocessing - Iteration #{}'.format(anipose_iter), style="color({})".format(3))
                
    #             if cal_video_frame_range[1] > session.numFrames:
    #                 console.rule('We moved the window all the way through the videos and Anipose still isn\'t happy, starting again from the begining with a shorter frame window', style="color({})".format(3))
    #                 frame_window_size = round(frame_window_size/2)
    #                 cal_video_frame_range = [0, frame_window_size]
                                    
    #                 if round(cal_video_frame_range[-1] * session.numFrames) < 1 or anipose_iter > 20:
    #                     Exception('Sorry, we weren\'t able to get AniPose to run successfully :( - Make sure your Charuco board was visible to each camera (not necessarily at the same time) and that there wasn\'t, like, a bunch of glare on it')
    #                     return
            
    #             console.rule('Trying Anipose calibration again with frame range {} - {}'.format(cal_video_frame_range[0], cal_video_frame_range[1]), style="color({})".format(3))
    #             createCalibrationVideos(session, cal_video_frame_range)

    #             try:
    #                 error,charuco_data, charuco_frames = cgroup.calibrate_videos(vidnames, board)
                    
    #                 if not spoof_anipose_fail_bool:
    #                     anipose_success=True
    #                 else:
    #                     cal_video_frame_range[0] = cal_video_frame_range[0] + round(session.numFrames*.1)
    #                     cal_video_frame_range[1] = cal_video_frame_range[1] + round(session.numFrames*.1)
    #             except:
    #                 cal_video_frame_range[0] = cal_video_frame_range[0] + round(session.numFrames*.1)
    #                 cal_video_frame_range[1] = cal_video_frame_range[1] + round(session.numFrames*.1)


    cgroup.dump(session.cameraCalFilePath) #JSM NOTE  - let's just use .yaml's unless there is some reason to use .toml



    session.cgroup = cgroup
    n_frames = calVideoFrameLength[1]-calVideoFrameLength[0]
    startframe = 0
    n_trackedPoints = 24

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

    charuco_fr_mar_xyz, charuco_reprojErr= reconstruct3D.reconstruct3D(
        session, charuco_nCams_nFrames_nImgPts_XY
    )

    mean_charuco_fr_mar_xyz = np.nanmean(charuco_fr_mar_xyz, axis=0)

    # charry_reshaped = charucoarray.reshape(session.numCams, -1, 2)

    # char_flat = cgroup.triangulate(charry_reshaped, progress=True)
    # charReprojerr_flat = cgroup.reprojection_error(char_flat, charry_reshaped, mean=True)

    # char_fr_mar_xyz = char_flat.reshape(n_frames, n_trackedPoints, 3)
    # charReprojErr_fr_mar_err = charReprojerr_flat.reshape(n_frames, n_trackedPoints)

    if session.debug:
        fig = plt.figure()
        # mean charuco position
        ax1 = fig.add_subplot(111, projection="3d")
        ax1.cla()
        x = mean_charuco_fr_mar_xyz[:][:, 0]
        y = mean_charuco_fr_mar_xyz[:][:, 1]
        z = mean_charuco_fr_mar_xyz[:][:, 2]
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
        # numPts = charuco_fr_mar_xyz.shape[1]
        # for pp in range(numPts):
        #     ax2.plot(charuco_fr_mar_xyz[:,pp,:])
        # ax2.set_title('Charuco Point positions over time')
        plt.show()

    np.save(session.dataArrayPath/'charuco_3d_points.npy', charuco_fr_mar_xyz)
    np.save(session.dataArrayPath/'charuco_3d_reprojErr.npy', charuco_reprojErr)

    return cgroup, charuco_fr_mar_xyz


def createCalibrationVideos(session, calVideoFrameLength):
    """ 
    Based on the desired length of the calibration videos (for the anipose functions), create new videos trimmed 
    to that specific length
    """  
    vidList = os.listdir(session.syncedVidPath)
    if len(calVideoFrameLength)==1:
        framelist = list(range(calVideoFrameLength))
    elif len(calVideoFrameLength)==2:
        framelist = list(range(calVideoFrameLength[0], calVideoFrameLength[1]))
    else:
        Exception('calVideoFrameLength must be either 1 or 2 elements long')
    
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
        print("Trimming " + cam_name + " to frames {}-{} for Anipose Calibration".format(framelist[0], framelist[-1]))
        for frame in track(framelist):
            cap.set(
                cv2.CAP_PROP_POS_FRAMES, frame
            )  # set the video to the frame that we need
            success, image = cap.read()
            out.write(image)
        cap.release()
        out.release()
