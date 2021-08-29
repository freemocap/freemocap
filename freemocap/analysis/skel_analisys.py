#%%
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

openPose3dDataPath = Path(r"C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2021-08-27_17_31_30\DataArrays\openPoseSkel_3d.npy")

mediaPipe3dDataPath = Path(r"C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2021-08-27_17_31_30\DataArrays\mediaPipeSkel_3d.npy")

openPose2dDataPath = Path(r"C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2021-08-27_17_31_30\DataArrays\openPoseData_2d.npy")

mediaPipe2dDataPath = Path(r"C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2021-08-27_17_31_30\DataArrays\mediaPipe_2d.npy")

#%%
mediaPipe_nCams_nFrames_nImgPts_XYC = np.load(mediaPipe2dDataPath)

mp_rToe_conf = mediaPipe_nCams_nFrames_nImgPts_XYC[:,:,32,2].transpose()
mp_nose_conf = mediaPipe_nCams_nFrames_nImgPts_XYC[:,:,0,2].transpose()


# %% hand/ball vs time
fig1 = plt.figure()
axToe = fig1.add_subplot(1,2,1)

axToe.plot(mp_rToe_conf, label='Right Toe')
axToe.set_xlabel('Time (frames)')
axToe.set_ylabel('Confidence')
axToe.legend()

axNose = fig1.add_subplot(1,2,2)

axNose.plot(mp_nose_conf, label='Nose')
axNose.set_xlabel('Time (frames)')
axNose.set_ylabel('Confidence')
axNose.legend()



# %%
