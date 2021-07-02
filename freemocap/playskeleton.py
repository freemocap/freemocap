# -*- coding: utf-8 -*-
"""
Created on Fri Feb 26 12:51:21 2021

@author: Rontc
"""

import numpy as np

# from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt
import cv2
from pathlib import Path
import pyqtgraph as pg

########################################################################################################################################
########################################################################################################################################
##
##  ███    ███  █████  ████████ ██████  ██       ██████  ████████ ██      ██ ██████
##  ████  ████ ██   ██    ██    ██   ██ ██      ██    ██    ██    ██      ██ ██   ██
##  ██ ████ ██ ███████    ██    ██████  ██      ██    ██    ██    ██      ██ ██████
##  ██  ██  ██ ██   ██    ██    ██      ██      ██    ██    ██    ██      ██ ██   ██
##  ██      ██ ██   ██    ██    ██      ███████  ██████     ██    ███████ ██ ██████
##
########################################################################################################################################
########################################################################################################################################


def ReplaySkeleton_matplotlib(
    session,
    vidType=1,
    startFrame=40,
    azimuth=-90,
    elevation=-80,
    useOpenPose=True,
    useMediaPipe=False,
    useDLC=False,
):

    
    mean_charuco_fr_mar_dim = np.load(session.dataArrayPath/'charuco_3d_points.npy')

    if useOpenPose:
        skel_fr_mar_dim = np.load(session.dataArrayPath / "openPoseSkel_3d.npy")

    if useMediaPipe:
        mediaPipe_skel_fr_mar_dim = np.load(
            session.dataArrayPath / "mediaPipeSkel_3d.npy"
        )

    if useDLC:
        dlc_fr_mar_dim = np.load(session.dataArrayPath / "deepLabCut_3d.npy")
        dlc0 = np.squeeze(dlc_fr_mar_dim[:, 0, :])
        dlc1 = np.squeeze(dlc_fr_mar_dim[:, 1, :])
        dlc2 = np.squeeze(dlc_fr_mar_dim[:, 2, :])
        ballTrailLen = 4

    if useOpenPose:
        imgPathList = session.session_settings['openPose_imgPathList']
  
    
    camImgPathList = {}
    for cam in range(session.numCams):
        camImgPathList[cam] = list(sorted(Path(imgPathList[cam]).glob('*.png')))
        #session.numFrames = len(camImgPathList[cam]) #will need to perhaps put a check in on whether numFrames between cameras are the same
    

# define Skeleton connections 
# head = [17, 15, 0, 16, 18]
    head = [ 15, 0, 16]
    spine = [0,1,8]
    rArm = [17, 15, 0, 16, 18]
    rArm = [4, 3, 2, 1]
    lArm = [1, 5, 6, 7]
    rLeg = [11, 10, 9, 8]
    lLeg = [14, 13, 12, 8]
    rFoot = [11, 23, 22, 11, 24]
    lFoot = [14, 20, 19, 14, 21]

    # Make some handy maps ;D
    rHandIDstart = 25
    lHandIDstart = rHandIDstart + 21

    thumb = np.array([0, 1, 2, 3, 4])
    index = np.array([0, 5, 6, 7, 8])
    bird = np.array([0, 9, 10, 11, 12])
    ring = np.array([0, 13, 14, 15, 16])
    pinky = np.array([0, 17, 18, 19, 20])

    fig = plt.figure(figsize=(11, 8))

    if vidType == 0:
        axMain = fig.add_subplot(111, projection="3d")
    elif vidType == 1:
        axMain = fig.add_subplot(121, projection="3d")
        axCam1 = fig.add_subplot(122)

    # fig.tight_layout(h_pad = 5)
    axMain.view_init(azim=azimuth, elev=elevation)
    plt.ion()
    for fr in range(startFrame, session.numFrames):
        fig.suptitle(["Frame# - ", str(fr)])
        axMain.cla()

        if vidType == 1:
            axCam1.cla()

        char_x = mean_charuco_fr_mar_dim[:][:, 0]
        char_y = mean_charuco_fr_mar_dim[:][:, 1]
        char_z = mean_charuco_fr_mar_dim[:][:, 2]

        # plot skeleton (openPose by default)

        sk_x = skel_fr_mar_dim[fr, :, 0]  # skeleton x data
        sk_y = skel_fr_mar_dim[fr, :, 1]  # skeleton y data
        sk_z = skel_fr_mar_dim[fr, :, 2]  # skeleton z data

        axMain.scatter3D(sk_x, sk_y, sk_z, marker=".", color="k", s=4.0)
        axMain.plot(
            sk_x[head], sk_y[head], sk_z[head], linestyle="-", color="g", linewidth=1.0
        )
        axMain.plot(
            sk_x[spine],
            sk_y[spine],
            sk_z[spine],
            linestyle="-",
            color="g",
            linewidth=1.0,
        )
        axMain.plot(
            sk_x[rArm], sk_y[rArm], sk_z[rArm], linestyle="-", color="r", linewidth=1.0
        )
        axMain.plot(
            sk_x[lArm], sk_y[lArm], sk_z[lArm], linestyle="-", color="b", linewidth=1.0
        )
        axMain.plot(
            sk_x[rLeg], sk_y[rLeg], sk_z[rLeg], linestyle="-", color="r", linewidth=1.0
        )
        axMain.plot(
            sk_x[lLeg], sk_y[lLeg], sk_z[lLeg], linestyle="-", color="b", linewidth=1.0
        )
        axMain.plot(
            sk_x[rFoot],
            sk_y[rFoot],
            sk_z[rFoot],
            linestyle="-",
            color="r",
            linewidth=1.0,
        )
        axMain.plot(
            sk_x[lFoot],
            sk_y[lFoot],
            sk_z[lFoot],
            linestyle="-",
            color="b",
            linewidth=1.0,
        )

        # plot handybois
        # right hand
        axMain.plot(
            sk_x[thumb + rHandIDstart],
            sk_y[thumb + rHandIDstart],
            sk_z[thumb + rHandIDstart],
            linestyle="-",
            color="r",
            linewidth=1.0,
        )
        axMain.plot(
            sk_x[index + rHandIDstart],
            sk_y[index + rHandIDstart],
            sk_z[index + rHandIDstart],
            linestyle="-",
            color="r",
            linewidth=1.0,
        )
        axMain.plot(
            sk_x[bird + rHandIDstart],
            sk_y[bird + rHandIDstart],
            sk_z[bird + rHandIDstart],
            linestyle="-",
            color="r",
            linewidth=1.0,
        )
        axMain.plot(
            sk_x[ring + rHandIDstart],
            sk_y[ring + rHandIDstart],
            sk_z[ring + rHandIDstart],
            linestyle="-",
            color="r",
            linewidth=1.0,
        )
        axMain.plot(
            sk_x[pinky + rHandIDstart],
            sk_y[pinky + rHandIDstart],
            sk_z[pinky + rHandIDstart],
            linestyle="-",
            color="r",
            linewidth=1.0,
        )

        # left hand
        axMain.plot(
            sk_x[thumb + lHandIDstart],
            sk_y[thumb + lHandIDstart],
            sk_z[thumb + lHandIDstart],
            linestyle="-",
            color="b",
            linewidth=1.0,
        )
        axMain.plot(
            sk_x[index + lHandIDstart],
            sk_y[index + lHandIDstart],
            sk_z[index + lHandIDstart],
            linestyle="-",
            color="b",
            linewidth=1.0,
        )
        axMain.plot(
            sk_x[bird + lHandIDstart],
            sk_y[bird + lHandIDstart],
            sk_z[bird + lHandIDstart],
            linestyle="-",
            color="b",
            linewidth=1.0,
        )
        axMain.plot(
            sk_x[ring + lHandIDstart],
            sk_y[ring + lHandIDstart],
            sk_z[ring + lHandIDstart],
            linestyle="-",
            color="b",
            linewidth=1.0,
        )
        axMain.plot(
            sk_x[pinky + lHandIDstart],
            sk_y[pinky + lHandIDstart],
            sk_z[pinky + lHandIDstart],
            linestyle="-",
            color="b",
            linewidth=1.0,
        )

        # plot mediapipe
        mp_sk_x = mediaPipe_skel_fr_mar_dim[fr, :, 0]  # skeleton x data
        mp_sk_y = mediaPipe_skel_fr_mar_dim[fr, :, 1]  # skeleton y data
        mp_sk_z = mediaPipe_skel_fr_mar_dim[fr, :, 2]  # skeleton z data
        axMain.scatter3D(mp_sk_x, mp_sk_y, mp_sk_z, marker=".", color="g", s=8.0)

        # plot deeplabcut

        dlc_x = dlc_fr_mar_dim[fr, :, 0]
        dlc_y = dlc_fr_mar_dim[fr, :, 1]
        dlc_z = dlc_fr_mar_dim[fr, :, 2]

        axMain.scatter3D(dlc_x, dlc_y, dlc_z, marker="o", color="r", s=24.0)

        # plot charuco grid
        axMain.scatter(char_x, char_y, char_z, marker="o")

        # #plot camera positions (I think...)
        # for camNum in range(len(session.cgroup.cameras)):
        #     axMain.scatter(session.cgroup.cameras[camNum].tvec[0], session.cgroup.cameras[camNum].tvec[1],  session.cgroup.cameras[camNum].tvec[2], marker = 'p')
        axRange = session.board.square_length * 10
        mx = np.nanmean(char_x)
        my = np.nanmean(char_y)
        mz = np.nanmean(char_z)

        axMain.set_xlim(mx - axRange, mx + axRange)
        axMain.set_ylim(my - axRange, my + axRange)
        axMain.set_zlim(mz - axRange, mz + axRange)

        axMain.set_xlabel("x")
        axMain.set_ylabel("y")
        axMain.set_zlabel("z")

        if vidType == 0:
            pass
        elif vidType == 1:
            axCam1.imshow(
                cv2.cvtColor(cv2.imread(str(camImgPathList[0][fr])), cv2.COLOR_BGR2RGB)
            )
            axCam1.axis("off")

        plt.pause(0.01)
        plt.show()

        frameName = str(fr).zfill(6)
        saveFrameName = "{}.png".format(frameName)
        saveFramePath = session.imOutPath / saveFrameName
        fig.savefig(saveFramePath)


########################################################################################################################################
########################################################################################################################################
###    ██████  ██████  ███████ ███    ██      ██████  ██
###   ██    ██ ██   ██ ██      ████   ██     ██       ██
###   ██    ██ ██████  █████   ██ ██  ██     ██   ███ ██
###   ██    ██ ██      ██      ██  ██ ██     ██    ██ ██
###    ██████  ██      ███████ ██   ████      ██████  ███████
########################################################################################################################################
########################################################################################################################################



def ReplaySkeleton_matplotlib( session,
                    vidType=1,
                    startFrame=40,
                    azimuth=-90,
                    elevation=-80,
                    useOpenPose=True,
                    useMediaPipe=False,
                    useDLC=False):

    session.imOutPath.mkdir(exist_ok = True)
    mean_charuco_fr_mar_dim = np.load(session.dataArrayPath/'charuco_3d_points.npy')


    if session.useMediaPipe:
        mediaPipe_skel_fr_mar_dim = np.load(session.dataArrayPath/'mediaPipeSkel_3d.npy')
        imgPathList = session.session_settings['mediaPipe_imgPathList']
        session.numCams = len(session.mediaPipe_imgPathList)

    if session.useOpenPose:
        skel_fr_mar_dim = np.load(session.dataArrayPath/'openPoseSkel_3d.npy')
        imgPathList = session.session_settings['openPose_imgPathList']
        #session.numCams = len(session.openPose_imgPathList)    
        
    if session.useDLC:
        dlc_fr_mar_dim = np.load(session.dataArrayPath / "deepLabCut_3d.npy")
        dlc0 = np.squeeze(dlc_fr_mar_dim[:, 0, :])
        dlc1 = np.squeeze(dlc_fr_mar_dim[:, 1, :])
        dlc2 = np.squeeze(dlc_fr_mar_dim[:, 2, :])
        ballTrailLen = 4

    camImgPathList = {}
    for cam in range(session.numCams):
        camImgPathList[cam] = list(sorted(Path(imgPathList[cam]).glob('*.png')))
        #session.numFrames = len(camImgPathList[cam]) #will need to perhaps put a check in on whether numFrames between cameras are the same
    

# define Skeleton connections 
# head = [17, 15, 0, 16, 18]
    head = [ 15, 0, 16]
    spine = [0,1,8]
    rArm = [4 ,3 ,2 ,1]
    lArm = [1, 5, 6, 7]
    rLeg = [11, 10, 9, 8]
    lLeg = [14, 13, 12, 8]
    rFoot = [11, 23, 22, 11, 24]
    lFoot = [14, 20, 19, 14, 21]

    # Make some handy maps ;D
    rHandIDstart = 25
    lHandIDstart = rHandIDstart + 21

    thumb = np.array([0, 1, 2, 3, 4])
    index = np.array([0, 5, 6, 7, 8])
    bird = np.array([0, 9, 10, 11, 12])
    ring = np.array([0, 13, 14, 15, 16])
    pinky = np.array([0, 17, 18, 19, 20])

    fig = plt.figure(figsize=(11, 8))

    if vidType == 0:
        axMain = fig.add_subplot(111, projection="3d")
    elif vidType == 1:
        axMain = fig.add_subplot(121, projection="3d")
        axCam1 = fig.add_subplot(122)

    # fig.tight_layout(h_pad = 5)
    axMain.view_init(azim=azimuth, elev=elevation)
    plt.ion()
    for fr in range(startFrame, session.numFrames):
        fig.suptitle(["Frame# - ", str(fr)])
        axMain.cla()

        if vidType == 1:
            axCam1.cla()

        char_x = mean_charuco_fr_mar_dim[:][:, 0]
        char_y = mean_charuco_fr_mar_dim[:][:, 1]
        char_z = mean_charuco_fr_mar_dim[:][:, 2]

        # plot skeleton (openPose by default)
        if session.useOpenPose:
            sk_x = skel_fr_mar_dim[fr, :, 0]  # skeleton x data
            sk_y = skel_fr_mar_dim[fr, :, 1]  # skeleton y data
            sk_z = skel_fr_mar_dim[fr, :, 2]  # skeleton z data

            axMain.scatter3D(sk_x, sk_y, sk_z, marker=".", color="k", s=4.0)
            axMain.plot(
                sk_x[head],
                sk_y[head],
                sk_z[head],
                linestyle="-",
                color="g",
                linewidth=1.0,
            )
            axMain.plot(
                sk_x[spine],
                sk_y[spine],
                sk_z[spine],
                linestyle="-",
                color="g",
                linewidth=1.0,
            )
            axMain.plot(
                sk_x[rArm],
                sk_y[rArm],
                sk_z[rArm],
                linestyle="-",
                color="r",
                linewidth=1.0,
            )
            axMain.plot(
                sk_x[lArm],
                sk_y[lArm],
                sk_z[lArm],
                linestyle="-",
                color="b",
                linewidth=1.0,
            )
            axMain.plot(
                sk_x[rLeg],
                sk_y[rLeg],
                sk_z[rLeg],
                linestyle="-",
                color="r",
                linewidth=1.0,
            )
            axMain.plot(
                sk_x[lLeg],
                sk_y[lLeg],
                sk_z[lLeg],
                linestyle="-",
                color="b",
                linewidth=1.0,
            )
            axMain.plot(
                sk_x[rFoot],
                sk_y[rFoot],
                sk_z[rFoot],
                linestyle="-",
                color="r",
                linewidth=1.0,
            )
            axMain.plot(
                sk_x[lFoot],
                sk_y[lFoot],
                sk_z[lFoot],
                linestyle="-",
                color="b",
                linewidth=1.0,
            )

            # plot handybois
            # right hand
            axMain.plot(
                sk_x[thumb + rHandIDstart],
                sk_y[thumb + rHandIDstart],
                sk_z[thumb + rHandIDstart],
                linestyle="-",
                color="r",
                linewidth=1.0,
            )
            axMain.plot(
                sk_x[index + rHandIDstart],
                sk_y[index + rHandIDstart],
                sk_z[index + rHandIDstart],
                linestyle="-",
                color="r",
                linewidth=1.0,
            )
            axMain.plot(
                sk_x[bird + rHandIDstart],
                sk_y[bird + rHandIDstart],
                sk_z[bird + rHandIDstart],
                linestyle="-",
                color="r",
                linewidth=1.0,
            )
            axMain.plot(
                sk_x[ring + rHandIDstart],
                sk_y[ring + rHandIDstart],
                sk_z[ring + rHandIDstart],
                linestyle="-",
                color="r",
                linewidth=1.0,
            )
            axMain.plot(
                sk_x[pinky + rHandIDstart],
                sk_y[pinky + rHandIDstart],
                sk_z[pinky + rHandIDstart],
                linestyle="-",
                color="r",
                linewidth=1.0,
            )

            # left hand
            axMain.plot(
                sk_x[thumb + lHandIDstart],
                sk_y[thumb + lHandIDstart],
                sk_z[thumb + lHandIDstart],
                linestyle="-",
                color="b",
                linewidth=1.0,
            )
            axMain.plot(
                sk_x[index + lHandIDstart],
                sk_y[index + lHandIDstart],
                sk_z[index + lHandIDstart],
                linestyle="-",
                color="b",
                linewidth=1.0,
            )
            axMain.plot(
                sk_x[bird + lHandIDstart],
                sk_y[bird + lHandIDstart],
                sk_z[bird + lHandIDstart],
                linestyle="-",
                color="b",
                linewidth=1.0,
            )
            axMain.plot(
                sk_x[ring + lHandIDstart],
                sk_y[ring + lHandIDstart],
                sk_z[ring + lHandIDstart],
                linestyle="-",
                color="b",
                linewidth=1.0,
            )
            axMain.plot(
                sk_x[pinky + lHandIDstart],
                sk_y[pinky + lHandIDstart],
                sk_z[pinky + lHandIDstart],
                linestyle="-",
                color="b",
                linewidth=1.0,
            )

        # plot mediapipe
        if session.useMediaPipe:
            mp_sk_x = mediaPipe_skel_fr_mar_dim[fr, :, 0]  # skeleton x data
            mp_sk_y = mediaPipe_skel_fr_mar_dim[fr, :, 1]  # skeleton y data
            mp_sk_z = mediaPipe_skel_fr_mar_dim[fr, :, 2]  # skeleton z data
            axMain.scatter3D(mp_sk_x, mp_sk_y, mp_sk_z, marker=".", color="g", s=8.0)

        # plot deeplabcut
        if session.useDLC:
            dlc_x = dlc_fr_mar_dim[fr, :, 0]
            dlc_y = dlc_fr_mar_dim[fr, :, 1]
            dlc_z = dlc_fr_mar_dim[fr, :, 2]

            axMain.scatter3D(dlc_x, dlc_y, dlc_z, marker="o", color="r", s=24.0)

        # plot charuco grid
        axMain.scatter(char_x, char_y, char_z, marker="o")

        # #plot camera positions (I think...)
        # for camNum in range(len(session.cgroup.cameras)):
        #     axMain.scatter(session.cgroup.cameras[camNum].tvec[0], session.cgroup.cameras[camNum].tvec[1],  session.cgroup.cameras[camNum].tvec[2], marker = 'p')
        axRange = session.board.square_length * 10
        mx = np.nanmean(char_x)
        my = np.nanmean(char_y)
        mz = np.nanmean(char_z)

        axMain.set_xlim(mx - axRange, mx + axRange)
        axMain.set_ylim(my - axRange, my + axRange)
        axMain.set_zlim(mz - axRange, mz + axRange)

        axMain.set_xlabel("x")
        axMain.set_ylabel("y")
        axMain.set_zlabel("z")

        if vidType == 0:
            pass
        elif vidType == 1:
            axCam1.imshow(
                cv2.cvtColor(cv2.imread(str(camImgPathList[0][fr])), cv2.COLOR_BGR2RGB)
            )
            axCam1.axis("off")

        plt.pause(0.01)
        plt.show()

        frameName = str(fr).zfill(6)
        saveFrameName = "{}.png".format(frameName)
        saveFramePath = session.imOutPath / saveFrameName
        fig.savefig(saveFramePath)
