# This is all very much a work in progress! More to come!
## ( We're working on it though! Stay tuned!)

# Installation
- Open an Anaconda Prompt (in Windows, or any terminal on Mac/Linux) and enter the following comands

`conda create -n freemocap-env python=3.7`

`conda activate freemocap-env`

`pip install freemocap -v`

`ipython`

```Python Console
import freemocap as fmc
fmc.RunMe() #this is where the magic happens.
```

https://user-images.githubusercontent.com/15314521/124694557-8069ea00-deaf-11eb-9328-3be27a4b1ea4.mp4

## Prerequisites - 
**Required**
* A Python 3.7 environment: We recommend installing Anaconda from here (https://www.anaconda.com/products/individual#Downloads) to create your Python environment.

* Two or more USB webcams attached to viable USB ports 
	*  (USB hubs typically don't work)
* Each recording must (for now) start with an unobstructed view of a  Charuco board generated with python commands (or equivalent):
	```
	import cv2
	
	aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_250) #note `cv2.aruco` can be installed via `pip install opencv-contrib-python`
	
	board = cv2.aruco.CharucoBoard_create(7, 5, 1, .8, aruco_dict)
	
	charuco_board_image = board.draw((2000,2000)) #`2000` is the resolution of the resulting image. Increase this number if printing a large board (bigger is better! Esp for large spaces!
	
	cv2.imwrite('charuco_board_image.png',charuco_board_image)
	
	```
**Optional**
If you would like to use OpenPose for body tracking, install Cude and the Windows Portable Demo of OpenPose. 

Install CUDA
https://developer.nvidia.com/cuda-downloads

Install OpenPose (Windows Portable Demo)
https://github.com/CMU-Perceptual-Computing-Lab/openpose/releases/tag/v1.6.0

Follow the GitHub Repository and/or Join the Discord (https://discord.gg/HX7MTprYsK) for updates!

# Stay Tuned for more soon!
