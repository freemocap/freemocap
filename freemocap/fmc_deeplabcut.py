# -*- coding: utf-8 -*-
"""
Created on Fri Feb 26 12:42:08 2021

@author: Rontc
"""
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yaml
from pathlib import Path
import h5py





def parseDeepLabCut(session): # NOTE this is assuming both the dlc config file and dlc data h5 foles are in the same folder specified in the session.dlcDataPath, if that is not the case either dlcconfig or h5files variable need to be changed

    dlcConfig = session.dlcConfigPath  #File path for dlcConfig file


    with open(dlcConfig) as configFile:
        #Open the config file
        configList = yaml.load(configFile, Loader = yaml.FullLoader)
        for item, doc in configList.items(): #For each item in the config file
            if item == 'bodyparts': #If the item is bodyparts
                bodypartList = doc #Set that list to a variable
            if item == 'skeleton': #If the item is skeleton
                skeletonList = doc #Set that list to a variable
            
    h5files =session.dlcDataPath.glob('*.h5') #Take all h5 files from folder
    
    numCams = int(session.numCams)#Get num of cams
    numFrames = session.numFrames+1#Get num of frames
    
    numPoints = len(bodypartList)# Get amount of points tracked
    dlcData_nCams_nFrames_nImgPts_XYC = np.ndarray([numCams, numFrames, numPoints, 3]) # Create empty array for dlc points

    nn=0#counter for each camera
    for data in h5files:#Loop throuxgh each camera
        with h5py.File(data) as f:#Open each h5 file
            fullDataGroup = f.get('df_with_missing')#Open main h5 group 
            dataTable = fullDataGroup.get('table')#Open datatable with all DLC tracked points
            for ii in range(len(dataTable)):#Loop through each frame
                dataFromOneFrame = dataTable[ii] #Assign frame to varible
                idx =(len(dataFromOneFrame[1])/3) #index for reshaping data
                sortedFrame = np.array(dataFromOneFrame[1]) #Put data in numoy array 
                dlcData_nCams_nFrames_nImgPts_XYC[nn,ii,:,:] =sortedFrame.reshape(int(idx),3) #Reshape the data into the correct form
        nn+=1
    
    if session.debug:
        fig = plt.figure()
        
        ax1 = fig.add_subplot(221)
        ax2 = fig.add_subplot(222)
        ax3 = fig.add_subplot(223)
        ax4 = fig.add_subplot(224)

        cam1im = session.firstImage_nCams_list[0]
        cam2im = session.firstImage_nCams_list[1]
        cam3im = session.firstImage_nCams_list[2]
        cam4im = session.firstImage_nCams_list[3]
        
        ax1.imshow(cam1im)
        ax1.plot(dlcData_nCams_nFrames_nImgPts_XYC[0,0,:,0],dlcData_nCams_nFrames_nImgPts_XYC[0,0,:,1])

        ax2.imshow(cam2im)
        ax2.plot(dlcData_nCams_nFrames_nImgPts_XYC[1,0,:,0],dlcData_nCams_nFrames_nImgPts_XYC[1,0,:,1])

        ax3.imshow(cam3im)
        ax3.plot(dlcData_nCams_nFrames_nImgPts_XYC[2,0,:,0],dlcData_nCams_nFrames_nImgPts_XYC[2,0,:,1])

        ax4.imshow(cam4im)
        ax4.plot(dlcData_nCams_nFrames_nImgPts_XYC[3,0,:,0],dlcData_nCams_nFrames_nImgPts_XYC[3,0,:,1])

        plt.show()

    np.save(session.dataArrayPath/'deepLabCutData_2d.npy', dlcData_nCams_nFrames_nImgPts_XYC)

    return dlcData_nCams_nFrames_nImgPts_XYC