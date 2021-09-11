#%% lol
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

dlcDataPath = Path(r"C:\Users\jonma\Dropbox\GitKrakenRepos\freemocap - Copy\Data\sesh_21-07-20_165209\DataArrays\deepLabCut_3d.npy")
openPoseDataPath = Path(r"C:\Users\jonma\Dropbox\GitKrakenRepos\freemocap - Copy\Data\sesh_21-07-20_165209\DataArrays\openPoseSkel_3d.npy")

dlc_fr_mar_xyz = np.load(dlcDataPath)
dlc_trajectories = [dlc_fr_mar_xyz[:,markerNum,:] for markerNum in range(dlc_fr_mar_xyz.shape[1])]    

skel_fr_mar_xyz = np.load(openPoseDataPath)
skel_trajectories = [skel_fr_mar_xyz[:,markerNum,:] for markerNum in range(skel_fr_mar_xyz.shape[1])]    

# %% hand/ball vs time
fig1 = plt.figure()
axX = fig1.add_subplot(2,1,1)
# axX.plot(dlc_trajectories[0][:,0], 'purple',linewidth=2)
axX.plot(dlc_trajectories[1][:,0], 'orange',linewidth=2)

axX.plot(skel_trajectories[4][:,0], 'red',linewidth=2)
axX.plot(skel_trajectories[7][:,0], 'blue',linewidth=2)
axX.set_title('X')
xlim = [300, 500]

axX.set_xlim(xlim)
axX.set_ylim([-300, 300])

axY = fig1.add_subplot(2,1,2)
# axY.plot(-dlc_trajectories[0][:,1], 'purple',linewidth=2)
axY.plot(-dlc_trajectories[1][:,1], 'orange',linewidth=2)

axY.plot(-skel_trajectories[4][:,1], 'red',linewidth=2)
axY.plot(-skel_trajectories[7][:,1], 'blue',linewidth=2)
axY.set_title('Y')
axY.set_xlim(xlim)
axY.set_ylim([-200, 500])

# axY = fig1.add_subplot(3,1,3)
# axY.plot(dlc_trajectories[0][:,2], 'purple',linewidth=2)
# axY.plot(skel_trajectories[4][:,2], 'red',linewidth=2)
# axY.set_title('Z')
# %% hand ball planar projections

fig2 = plt.figure()
axPlanar = fig2.add_subplot( )
frRange = np.arange(xlim[0], xlim[1], 1)

ballX = -dlc_trajectories[0][frRange,0]
ballY = -dlc_trajectories[0][frRange,1]

rHandX = -skel_trajectories[4][frRange,0]
rHandY = -skel_trajectories[4][frRange,1]

lHandX = -skel_trajectories[7][frRange,0]
lHandY = -skel_trajectories[7][frRange,1]

axPlanar.plot(ballX, ballY, 'purple',linewidth=2)
axPlanar.plot(rHandX, rHandY, 'red',linewidth=2)
axPlanar.plot(lHandX, lHandY, 'blue',linewidth=2)

#%% hand vs ball?

fig3 = plt.figure()
axPhase = fig3.add_subplot( )
frRange = np.arange(xlim[0], xlim[0]+300, 1)
ballX = -dlc_trajectories[0][frRange,0]
ballY = -dlc_trajectories[0][frRange,1]

rHandX = -skel_trajectories[4][frRange,0]
rHandY = -skel_trajectories[4][frRange,1]

lHandX = -skel_trajectories[7][frRange,0]
lHandY = -skel_trajectories[7][frRange,1]


rHandXvBallX = rHandX - ballX
rHandYvBallY = rHandY - ballY

lHandXvBallX = lHandX - ballX
lHandYvBallY = lHandY - ballY

# axPhase.plot(ballX, rHandX, 'purple',linewidth=2)
# axPhase.plot(ballY, rHandY, 'red',linewidth=2)
axPhase.plot(rHandXvBallX, rHandYvBallY, 'red',linewidth=2)
axPhase.plot(lHandXvBallX, lHandYvBallY, 'blue',linewidth=2)
# axPhase.plot(ballY, lHandY, 'forestgreen',linewidth=2)

#%%
# %%
