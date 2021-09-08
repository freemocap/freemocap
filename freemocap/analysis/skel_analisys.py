#%%
%matplotlib

import numpy as np

import matplotlib.pyplot as plt
import mpl_toolkits.mplot3d.axes3d as p3
import matplotlib.animation as animation
from matplotlib.widgets import Slider
import cv2 

import copy
from pathlib import Path

#RICH CONSOLE STUFF
from rich import pretty
pretty.install() #makes all print statement output pretty
from rich import inspect
from rich.console import Console
console = Console()  
from rich.traceback import install as rich_traceback_install
from rich.markdown import Markdown

# %% load dlc data 

openPose3dDataPath = Path(r"C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2021-09-07_09_09_56\DataArrays\openPoseSkel_3d.npy")

mediaPipe3dDataPath = Path(r"C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2021-09-07_09_09_56\DataArrays\mediaPipeSkel_3d.npy")
mediaPipe3dReprojPath = Path(r"C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2021-09-07_09_09_56\DataArrays\mediaPipeSkel_reprojErr.npy")

openPose2dDataPath = Path(r"C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2021-09-07_09_09_56\DataArrays\openPoseData_2d.npy")

mediaPipe2dDataPath = Path(r"C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2021-09-07_09_09_56\DataArrays\mediaPipe_2d.npy")

#%% pull out 2d data
mediaPipe_nCams_nFrames_nImgPts_XYC = np.load(mediaPipe2dDataPath)

mp_rToe_conf = mediaPipe_nCams_nFrames_nImgPts_XYC[:,:,32,2].transpose()
mp_nose_conf = mediaPipe_nCams_nFrames_nImgPts_XYC[:,:,0,2].transpose()

#%% pull out 3d reproj error

mediaPipe_ReProjErr= np.load(mediaPipe3dReprojPath)

mediaPipe_meanReproj_fr = np.nanmean(mediaPipe_ReProjErr,0)


# %% hand/ball vs time

camLabels = ["Cam#{}".format(str(camNum)) for camNum in range(mediaPipe_nCams_nFrames_nImgPts_XYC.shape[0])]

fig1 = plt.figure()
axToe = fig1.add_subplot(1,3,1)

axToe.plot(mp_rToe_conf, label='rToe')
axToe.set_xlabel('Time (frames)')
axToe.set_ylabel('Nose Confidence')
axToe.legend()

axNose = fig1.add_subplot(1,3,2)

axNose.plot(mp_nose_conf, label='Nose')
axNose.set_xlabel('Time (frames)')
axNose.set_ylabel('Nose Confidence')
axNose.legend()

axSkelReProj = fig1.add_subplot(1,3,3)

axSkelReProj.plot(mediaPipe_meanReproj_fr, label='ReprojErr')
axSkelReProj.set_xlabel('Time (frames)')
axSkelReProj.set_ylabel('Mean ReprojErr')
axSkelReProj.legend()


# %%
