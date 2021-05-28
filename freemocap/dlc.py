# -*- coding: utf-8 -*-
"""
Created on Fri Feb 26 12:42:08 2021

@author: Rontc
"""
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl


def ParseDLCdata(sesh): #note this is all sloppy af just to get a completed video together. Latter iterations will use DLC methods and be smarter about Pandas Dataframs and whatnot
        
    
        dlcCSVPaths = sesh.dlcDataPath.glob('*.csv') #NOTE - Super hacky here. Need to fix these methods (replace with DLC native functions?)
        
        numCams = int(sesh.numCams)
        numFrames = sesh.numFrames+1
        
        if sesh.sessionID == 'test6_01_21a': #NOTE - THIS IS DUMB AND BAD
            numCols =  8 #this is the number of tracked points in DLC - hardcoding for now because I am a bad person 
        else:
            numCols = 3 #NOTE - AGAIN< THIS IS DUMB AND BAD >

        dlc_nCams_nFrames_nImgPts_XYC = np.ndarray([numCams, numFrames, numCols, 3])
        dlc_nCams_nFrames_nImgPts_XYC.fill(np.nan)
        camNum = -1
        for thisCSVpath in dlcCSVPaths:     #triple nested for loop so I don't have to figure out np.reshape lol
            camNum += 1
            thisCam_dlcDataFrame = pd.read_csv(thisCSVpath, skiprows=1, header = [0,1]) #NOTE - This is dumb and bad. No need for this pandas dataframe, I think 
            thisCam_dlcNumpy = thisCam_dlcDataFrame.to_numpy()
            thisCam_dlcNumpy = thisCam_dlcNumpy[:, 1:] #remove first column (frame numbers)

            for thisFrame in range(thisCam_dlcNumpy.shape[0]):
                for thisImgPt in range(0,thisCam_dlcNumpy.shape[1],3):
                    dlc_nCams_nFrames_nImgPts_XYC[camNum,thisFrame,int(thisImgPt/3), 0] = thisCam_dlcNumpy[thisFrame, thisImgPt]
                    dlc_nCams_nFrames_nImgPts_XYC[camNum,thisFrame,int(thisImgPt/3), 1] = thisCam_dlcNumpy[thisFrame, thisImgPt+1]
                    dlc_nCams_nFrames_nImgPts_XYC[camNum,thisFrame,int(thisImgPt/3), 2] = thisCam_dlcNumpy[thisFrame, thisImgPt+2]
        

        if sesh.debug:
            fig = plt.figure()
            
            ax1 = fig.add_subplot(221)
            ax2 = fig.add_subplot(222)
            ax3 = fig.add_subplot(223)
            ax4 = fig.add_subplot(224)

            cam1im = sesh.firstImage_nCams_list[0]
            cam2im = sesh.firstImage_nCams_list[1]
            cam3im = sesh.firstImage_nCams_list[2]
            cam4im = sesh.firstImage_nCams_list[3]
            
            ax1.imshow(cam1im)
            ax1.plot(dlc_nCams_nFrames_nImgPts_XYC[0,0,:,0],dlc_nCams_nFrames_nImgPts_XYC[0,0,:,1])

            ax2.imshow(cam2im)
            ax2.plot(dlc_nCams_nFrames_nImgPts_XYC[1,0,:,0],dlc_nCams_nFrames_nImgPts_XYC[1,0,:,1])

            ax3.imshow(cam3im)
            ax3.plot(dlc_nCams_nFrames_nImgPts_XYC[2,0,:,0],dlc_nCams_nFrames_nImgPts_XYC[2,0,:,1])

            ax4.imshow(cam4im)
            ax4.plot(dlc_nCams_nFrames_nImgPts_XYC[3,0,:,0],dlc_nCams_nFrames_nImgPts_XYC[3,0,:,1])

            plt.show()
        
        sesh.dlc_nCams_nFrames_nImgPts_XYC = dlc_nCams_nFrames_nImgPts_XYC