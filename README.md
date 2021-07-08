# This is all very much a work in progress! More to come!


https://user-images.githubusercontent.com/15314521/124694557-8069ea00-deaf-11eb-9328-3be27a4b1ea4.mp4

# Installation

## Prerequisites - 
* Install Anaconda
 	- https://www.anaconda.com/products/individual#Downloads
* Install CUDA
 	- https://developer.nvidia.com/cuda-downloads
* Install OpenPose (Windows Portable Demo)
  - https://github.com/CMU-Perceptual-Computing-Lab/openpose/releases/tag/v1.6.0  
	- This can be complicated, so I'll need to add more instructions here!
* Two or more USB webcams attached to viable USB ports 
	*  (USB hubs typically don't work)
* Each recording must (for now) start with an unobstructed view of a  Charuco board generated with python commands:
	```
	import cv2
	
	aruco_dict = aruco.Dictionary_get(cv2.aruco.DICT_4X4_250) #note `cv2.aruco` can be installed via `pip install opencv-contrib-python`
	
	board = cv2.aruco.CharucoBoard_create(7, 5, 1, .8, aruco_dict)
	
	charuco_board_image = board.draw((2000,2000))
	
	cv2.imwrite('charuco_board_image.png',charuco_board_image)
	
	```

## Installation instructions (but FYI - This still isn't *really* in a state that's usable for outside users yet 😅 We're working on it though, stay tuned!)
- Open an Anaconda Prompt (in Windows, or any terminal on Mac/Linux) and enter the following comands

`conda create -n freemocap-env python=3.7`

`conda activate freemocap-env`

`pip install freemocap -v`

`ipython`

```Python
import freemocap as fmc
fmc.RunMe() #this is where the magic happens
```




Follow the GitHub Repository and/or Join the Discord (https://discord.gg/HX7MTprYsK) for updates!

#Stay Tuned for more soon!
