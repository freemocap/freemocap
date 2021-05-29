# -*- coding: utf-8 -*-
"""
Created on Fri Feb 26 12:51:21 2021

@author: Rontc
"""

import numpy as np 
#from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt
import matplotlib as mpl
import cv2
from pathlib import Path
#from glob import glob

# def PlaySkeleton(session, vidType):

#         # vidType = 0 #No Cam Ims
#         # vidType = 1 #Only Cam1 im
#         # vidType = 2 #All Cam Ims

#         #where to put the output images (later will be justa video)
        
        
#         #os.chdir(imOutPath)

    

        
#         #set axis limits based on charuco board
#         # mx = np.mean(charuco_x)
#         # my = np.mean(charuco_y)
#         # mz = np.mean(charuco_z)

#         #set up figure
#         # fig = plt.figure(figsize=([11,8]))

#         # if vidType==0:
#         #     axMain = fig.add_subplot(111,projection='3d')
#         # elif vidType == 1:
#         #     axMain = fig.add_subplot(121,projection='3d')
#         #     axCam1 = fig.add_subplot(122)
#         # elif vidType == 2:
#         #     figGridSpec = fig.add_gridspec(2,4)
#         #     axMain = fig.add_subplot(figGridSpec[:2,:2],projection='3d')
#         #     axCam1 = fig.add_subplot(figGridSpec[0,2])
#         #     axCam2 = fig.add_subplot(figGridSpec[0,3])
#         #     axCam3 = fig.add_subplot(figGridSpec[1,2])
#         #     axCam4 = fig.add_subplot(figGridSpec[1,3])
            
   


#         ##############################################################################################
#         ##Frame-by-frame animation loop starts here
#         ##############################################################################################

#     # fig = plt.figure()
#     # ax = fig.add_subplot(111,projection='3d')
#     # ax.cla()
#     # x = session.mean_charuco_fr_mar_dim[:][:,0]
#     # y = session.mean_charuco_fr_mar_dim[:][:,1]
#     # z = session.mean_charuco_fr_mar_dim[:][:,2]
#     # ax.scatter(x,y,z, marker='o')
#     # plt.show()

# # define Skeleton connections 
# # head = [17, 15, 0, 16, 18]
#     head = [ 15, 0, 16]
#     spine = [0,1,8]
#     rArm = [17, 15, 0, 16, 18]
#     rArm = [4 ,3 ,2 ,1]
#     lArm = [1, 5, 6, 7]
#     rLeg = [11 ,10, 9, 8]
#     lLeg = [14 ,13 ,12, 8]
#     rFoot = [11, 23,22, 11, 24]
#     lFoot = [14, 20, 19, 14, 21]

#     #Make some handy maps ;D
#     rHandIDstart = 25 
#     lHandIDstart = rHandIDstart+21

#     thumb = np.array([0,1,2,3,4])
#     index = np.array([0, 5,6,7,8])
#     bird = np.array([0, 9,10,11,12])
#     ring = np.array([0, 13,14,15,16])
#     pinky = np.array([0, 17,18,19,20])


#     fig = plt.figure(figsize=(8,6))
#     axMain = fig.add_subplot(111,projection='3d')
#     plt.ion()
#     for fr in range(session.numFrames):
#         fig.suptitle(['Frame# - ', str(fr)])
#         axMain.cla()
#         char_x = session.mean_charuco_fr_mar_dim[:][:,0]
#         char_y = session.mean_charuco_fr_mar_dim[:][:,1]
#         char_z = session.mean_charuco_fr_mar_dim[:][:,2]

#         if session.useOpenPose:         
#             sk_x = session.skel_fr_mar_dim[fr,:,0] #skeleton x data
#             sk_y = session.skel_fr_mar_dim[fr,:,1] #skeleton y data
#             sk_z = session.skel_fr_mar_dim[fr,:,2] #skeleton z data

#             axMain.scatter3D(sk_x,sk_y,sk_z, marker='.',color = 'k', s=4.)
#             axMain.plot(sk_x[head],sk_y[head],sk_z[head], linestyle='-', color='g', linewidth = 1.)
#             axMain.plot(sk_x[spine],sk_y[spine],sk_z[spine], linestyle='-', color = 'g', linewidth = 1.)
#             axMain.plot(sk_x[rArm],sk_y[rArm],sk_z[rArm], linestyle='-', color = 'r', linewidth = 1.)
#             axMain.plot(sk_x[lArm],sk_y[lArm],sk_z[lArm], linestyle='-', color = 'b', linewidth = 1.)
#             axMain.plot(sk_x[rLeg],sk_y[rLeg],sk_z[rLeg], linestyle='-', color = 'r', linewidth = 1.)
#             axMain.plot(sk_x[lLeg],sk_y[lLeg],sk_z[lLeg], linestyle='-', color = 'b', linewidth = 1.)
#             axMain.plot(sk_x[rFoot],sk_y[rFoot],sk_z[rFoot], linestyle='-', color = 'r', linewidth = 1.)
#             axMain.plot(sk_x[lFoot],sk_y[lFoot],sk_z[lFoot], linestyle='-', color = 'b', linewidth = 1.)

#                         # plot handybois
#             # right hand
#             axMain.plot(sk_x[thumb+rHandIDstart],sk_y[thumb+rHandIDstart],sk_z[thumb+rHandIDstart], linestyle='-', color = 'r', linewidth = 1.)
#             axMain.plot(sk_x[index+rHandIDstart],sk_y[index+rHandIDstart],sk_z[index+rHandIDstart], linestyle='-', color = 'r', linewidth = 1.)
#             axMain.plot(sk_x[bird+rHandIDstart],sk_y[bird+rHandIDstart],sk_z[bird+rHandIDstart], linestyle='-', color = 'r', linewidth = 1.)
#             axMain.plot(sk_x[ring+rHandIDstart],sk_y[ring+rHandIDstart],sk_z[ring+rHandIDstart], linestyle='-', color = 'r', linewidth = 1.)
#             axMain.plot(sk_x[pinky+rHandIDstart],sk_y[pinky+rHandIDstart],sk_z[pinky+rHandIDstart], linestyle='-', color = 'r', linewidth = 1.)

#             #left hand
#             axMain.plot(sk_x[thumb+lHandIDstart],sk_y[thumb+lHandIDstart],sk_z[thumb+lHandIDstart], linestyle='-', color = 'b', linewidth = 1.)
#             axMain.plot(sk_x[index+lHandIDstart],sk_y[index+lHandIDstart],sk_z[index+lHandIDstart], linestyle='-', color = 'b', linewidth = 1.)
#             axMain.plot(sk_x[bird+lHandIDstart],sk_y[bird+lHandIDstart],sk_z[bird+lHandIDstart], linestyle='-', color = 'b', linewidth = 1.)
#             axMain.plot(sk_x[ring+lHandIDstart],sk_y[ring+lHandIDstart],sk_z[ring+lHandIDstart], linestyle='-', color = 'b', linewidth = 1.)
#             axMain.plot(sk_x[pinky+lHandIDstart],sk_y[pinky+lHandIDstart],sk_z[pinky+lHandIDstart], linestyle='-', color = 'b', linewidth = 1.)
       
#         axMain.scatter(char_x,char_y,char_z, marker='o')

#         axMain.set_xbound(lower=-150, upper=150)
#         axMain.set_ybound(lower=-150, upper=150)
#         axMain.set_zbound(lower=-150, upper=150)

#         #imName = [session.sessionID + '_frame' + fr.zfill(6)]
#         frameName = str(fr).zfill(6)
#         saveFrameName = '{}.png'.format(frameName)
#         saveFramePath = session.imOutPath/saveFrameName
#         fig.savefig(saveFramePath)# , bbox_inches = 'tight')

#         plt.pause(0.01)
#         plt.show()


def ReplaySkeleton(session, vidType, startframe,azimuth,elevation):
    camImgPathList = {}
    for cam in range(session.numCams):
        camImgPathList[cam] = list(sorted(Path(session.openPose_imgPathList[cam]).glob('*.png')))
        session.numFrames = len(camImgPathList[cam]) #will need to perhaps put a check in on whether numFrames between cameras are the same
    

# define Skeleton connections 
# head = [17, 15, 0, 16, 18]
    head = [ 15, 0, 16]
    spine = [0,1,8]
    rArm = [17, 15, 0, 16, 18]
    rArm = [4 ,3 ,2 ,1]
    lArm = [1, 5, 6, 7]
    rLeg = [11 ,10, 9, 8]
    lLeg = [14 ,13 ,12, 8]
    rFoot = [11, 23,22, 11, 24]
    lFoot = [14, 20, 19, 14, 21]

    #Make some handy maps ;D
    rHandIDstart = 25 
    lHandIDstart = rHandIDstart+21

    thumb = np.array([0,1,2,3,4])
    index = np.array([0, 5,6,7,8])
    bird = np.array([0, 9,10,11,12])
    ring = np.array([0, 13,14,15,16])
    pinky = np.array([0, 17,18,19,20])


    fig = plt.figure(figsize=(11,8))

    if vidType == 0:
        axMain = fig.add_subplot(111,projection='3d')
    elif vidType == 1:
        axMain = fig.add_subplot(121,projection='3d')
        axCam1 = fig.add_subplot(122)

    # fig.tight_layout(h_pad = 5)
    axMain.view_init(azim = azimuth, elev= elevation)
    plt.ion()
    for fr in range(startframe,session.numFrames):
        fig.suptitle(['Frame# - ', str(fr)])
        axMain.cla()

        if vidType == 1:
            axCam1.cla()


        char_x = session.mean_charuco_fr_mar_dim[:][:,0]
        char_y = session.mean_charuco_fr_mar_dim[:][:,1]
        char_z = session.mean_charuco_fr_mar_dim[:][:,2]

        if session.useOpenPose:         
            sk_x = session.skel_fr_mar_dim[fr,:,0] #skeleton x data
            sk_y = session.skel_fr_mar_dim[fr,:,1] #skeleton y data
            sk_z = session.skel_fr_mar_dim[fr,:,2] #skeleton z data

            axMain.scatter3D(sk_x,sk_y,sk_z, marker='.',color = 'k', s=4.)
            axMain.plot(sk_x[head],sk_y[head],sk_z[head], linestyle='-', color='g', linewidth = 1.)
            axMain.plot(sk_x[spine],sk_y[spine],sk_z[spine], linestyle='-', color = 'g', linewidth = 1.)
            axMain.plot(sk_x[rArm],sk_y[rArm],sk_z[rArm], linestyle='-', color = 'r', linewidth = 1.)
            axMain.plot(sk_x[lArm],sk_y[lArm],sk_z[lArm], linestyle='-', color = 'b', linewidth = 1.)
            axMain.plot(sk_x[rLeg],sk_y[rLeg],sk_z[rLeg], linestyle='-', color = 'r', linewidth = 1.)
            axMain.plot(sk_x[lLeg],sk_y[lLeg],sk_z[lLeg], linestyle='-', color = 'b', linewidth = 1.)
            axMain.plot(sk_x[rFoot],sk_y[rFoot],sk_z[rFoot], linestyle='-', color = 'r', linewidth = 1.)
            axMain.plot(sk_x[lFoot],sk_y[lFoot],sk_z[lFoot], linestyle='-', color = 'b', linewidth = 1.)

                        # plot handybois
            # right hand
            axMain.plot(sk_x[thumb+rHandIDstart],sk_y[thumb+rHandIDstart],sk_z[thumb+rHandIDstart], linestyle='-', color = 'r', linewidth = 1.)
            axMain.plot(sk_x[index+rHandIDstart],sk_y[index+rHandIDstart],sk_z[index+rHandIDstart], linestyle='-', color = 'r', linewidth = 1.)
            axMain.plot(sk_x[bird+rHandIDstart],sk_y[bird+rHandIDstart],sk_z[bird+rHandIDstart], linestyle='-', color = 'r', linewidth = 1.)
            axMain.plot(sk_x[ring+rHandIDstart],sk_y[ring+rHandIDstart],sk_z[ring+rHandIDstart], linestyle='-', color = 'r', linewidth = 1.)
            axMain.plot(sk_x[pinky+rHandIDstart],sk_y[pinky+rHandIDstart],sk_z[pinky+rHandIDstart], linestyle='-', color = 'r', linewidth = 1.)

            #left hand
            axMain.plot(sk_x[thumb+lHandIDstart],sk_y[thumb+lHandIDstart],sk_z[thumb+lHandIDstart], linestyle='-', color = 'b', linewidth = 1.)
            axMain.plot(sk_x[index+lHandIDstart],sk_y[index+lHandIDstart],sk_z[index+lHandIDstart], linestyle='-', color = 'b', linewidth = 1.)
            axMain.plot(sk_x[bird+lHandIDstart],sk_y[bird+lHandIDstart],sk_z[bird+lHandIDstart], linestyle='-', color = 'b', linewidth = 1.)
            axMain.plot(sk_x[ring+lHandIDstart],sk_y[ring+lHandIDstart],sk_z[ring+lHandIDstart], linestyle='-', color = 'b', linewidth = 1.)
            axMain.plot(sk_x[pinky+lHandIDstart],sk_y[pinky+lHandIDstart],sk_z[pinky+lHandIDstart], linestyle='-', color = 'b', linewidth = 1.)
       
        #plot charuco grid
        axMain.scatter(char_x,char_y,char_z, marker='o')

        # #plot camera positions (I think...)
        # for camNum in range(len(session.cgroup.cameras)):
        #     axMain.scatter(session.cgroup.cameras[camNum].tvec[0], session.cgroup.cameras[camNum].tvec[1],  session.cgroup.cameras[camNum].tvec[2], marker = 'p')

        axMain.set_xlabel('x')
        axMain.set_ylabel('y')
        axMain.set_zlabel('z')

        axMain.set_xlim(-1000,1000)
        axMain.set_ylim(-1000,1000)
        axMain.set_zlim(1000,3000)
        
        if vidType ==0:
                pass
        elif vidType == 1:
                axCam1.imshow(cv2.cvtColor(cv2.imread(str(camImgPathList[0][fr])),cv2.COLOR_BGR2RGB))
                axCam1.axis('off')

        plt.pause(0.01)
        plt.show()

        frameName = str(fr).zfill(6)
        saveFrameName = '{}.png'.format(frameName)
        saveFramePath = session.imOutPath/saveFrameName
        fig.savefig(saveFramePath )
