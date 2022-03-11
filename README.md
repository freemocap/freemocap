
https://user-images.githubusercontent.com/15314521/124694557-8069ea00-deaf-11eb-9328-3be27a4b1ea4.mp4

# This is all very much a work in progress! More to come!
## (As of March 2022) We're currently working on building a proper API with documentation, but for now enjoy this pile of semi-spaghettified code and sloppy ReadMe 😅

___________________________________
___

## Prerequisites - 
**Required**
* Windows only for now (sorry! Mac and Linux support coming very soon!😅)
* A Python 3.7 environment - 
  * We recommend installing Anaconda from here (https://www.anaconda.com/products/individual#Downloads) to create your Python environment.

* Two or more USB webcams attached to viable USB ports 
	*  USB hubs typically don't work
	*  Note that two cameras is the minimum reuired for 3d reconstruction. However, with just two views, many points will be occluded/not visible to both cameras. For better performance, use three or four cameras
* Each recording must (for now)  an unobstructed view of a  Charuco board within the first few seconds of recording (See below).
____
____
# Installation
Open an Anaconda-enabled command prompt or powershell window and perform the following steps:

1) Create a Python3.7 Anaconda environment
``` 
$ conda create -n freemocap-env python=3.7
``` 

2) Activate that newly created environment
```
$ conda activate freemocap-env
```
3) Install freemocap  from PyPi using `pip`
```
$ pip install freemocap
```
That should be it!
___
___
# Basic Usage



 ##  HOW TO CREATE A *NEW* `FreeMoCap` RECORDING SESSION

tl;dr- Activate the the freemocap Python environment and run the following lines of code (either in a script or in a console)

```python
import freemocap as fmc
fmc.RunMe()
```

This two-line script is a copy of the `freemocap_runme_script.py` file, which can be run by entering the following command into a command prompt or powershell: 
```
(freemoocap-env)$ python freemocap_runme_script.py
```
## In a bit more detail- 

 ### 1)  In an Anaconda enabled Command Prompt, PowerShell, or Windows Terminal window 
- You will know if it's `Anaconda Enabled` because you will see a little `(base)` to the left of each line, which denotes that your `(base)` environment is currently active.
-  We recommend Windows Terminal so you can enjoy all the [Rich](https://github.com/willmcgugan/rich)✨ formatted text output, but you'll need to do a bit of work to connect it to Anaconda (e.g. [these instructions](https://dev.to/azure/easily-add-anaconda-prompt-in-windows-terminal-to-make-life-better-3p6j) )
   - If that seems intimidating (or just too much work), just press the `Windows` key, type `Anaconda Prompt` and run everything from there.
   
 ###  2) Activate your freemocap environment 
  - e.g. if your freemocap environment is named `freemocap-env`, type:
  ```
  (base)$ conda activate freemocap-env
  ```
  - If successful, the `(base)` to the left of each line will change to `(freemocap-env)`, indicating that your freemocap environment is now active (type `conda info --envs` or `conda info -e` for a list of all available environments)

### 3) Activate an `ipython` console
   - Activate  an instance of an `ipython` console by typing `ipython` into the command window and pressing 'Enter'
```
(freemocap-env)$ ipython
```
### 4)  Within the `ipython` console, import the `freemocap` package as `fmc`

```Python
[1]: import freemocap as fmc
```

### 5) Execute the `fmc.RunMe()` command (with default parameters, see [#runme-input-parameters](#runme-input-parameters) for more info)

```python
[2]: fmc.RunMe() #<-this is where the magic happens!
```

### 6) Follow instructions in the Command window and pop-up GUI windows!
---✨💀✨---.

---
___

## HOW TO REPROCESS A PREVIOUSLY RECORDED `FreeMoCap` RECORDING SESSION

You can re-start the processing pipeline from any of the following processing stages (defined below)by specifying the `SessionID` desired `stage` in the call to `fmc.RunMe()`

So to process the session named `sesh_2021-11-21_19_42_07` starting from stage 3, run:
```python
import freemocap as fmc
fmc.RunMe(sessionID="sesh_2021-11-21_19_42_07", stage=3)
```

Note - if you leave `sessionID` unspecified but set `stage` to a number higher than 1, it will attempt to use the last recorded session

___

## [Processing stages](#processing-stages)  - 

 - **Stage 1 - Record Videos**
   -  Record raw videos from attached USB webcams and timestamps for each frame 
   -  Raw Videos saved to `FreeMoCap_Data/[Session Folder]/RawVideos`

 - **Stage 2 - Synchronize Videos**
   - Use recorded timestamps to re-save raw videos as synchronized videos (same start and end and same number of frames). Videos saved to 
   - Synchronized Videos saved to `FreeMoCap_Data/[Session Folder]/SynchedVideos`


 - **Stage 3 - Calibrate Capture Volume**
   -   Use [Anipose](https://anipose.org)'s [Charuco-based](https://docs.opencv.org/3.4/df/d4a/tutorial_charuco_detection.html) calibration method to determine the location of each camera during a recording session and calibrate the capture volume
   -   Calibration info saved to `[sessionID]_calibration.toml` and `[sessionID]_calibration.pickle` 


-   **Stage 4 - Track 2D points in videos and Reconstruct 3D** <-This is where the magic happens ✨
    -   Apply user specified tracking algorithms to Synchronized videos (currently supporting MediaPipe, OpenPose, and DeepLabCut) to generate 2D data 
        -   Save to `FreeMoCap_Data/[Session Folder]/DataArrays/` folder (e.g. `mediaPipeData_2d.npy`)
    -   Combine 2d data from each camera with calibration data from Stage 3 to reconstruct the 3d trajectory of each tracked point
        -   Save to `/DataArrays` folder (e.g. `openPoseSkel_3d.npy`)
    -   NOTE - you might think it would make sense to separate the 2d tracking and 3d reconstruction into different stages, but the way the code is currently set up it's cleaner to combine them into the same processing stage ¯\\\_(ツ)_/¯

-   **Stage 5 - Use Blender to generate output data files (EXPERIMENTAL, optional, requires [Blender](https://blender.org) installed. set `fmc.RunMe(useBlender=False)` to skip)**
    -   Hijack a user-installed version of [Blender](https://blender.org) to format raw mocap data into various other formats, including `.blend`, `.fbx`, `.usd`, `.gltf`, etc.
    -   Save each filetype to main session folder
    -   NOTE - This is a new feature and still in a active development (as of 2021-11-28). It is still experimental and will be updating soon!


-   **Stage 6 - Save Skeleton Animation!**
    -   Create a [Matplotlib](https://matplotlib.org) based output animation video.
    -   System will first attempt to use an [ffmpeg](https://ffmpeg.org) based video exporter, and if that fails (usually because ffmpeg is not installed) it will revert to a (much slower) alternative and print instructions on how to install `ffmpeg`
        -  (basically it points you here - https://www.wikihow.com/Install-FFmpeg-on-Windows)
     -  Saves Animation video to: `[Session Folder]/[SessionID]_animVid.mp4`
     
____
____
## `fmc.RunMe()` Specify recording session parameters 
___
The `fmc.RunMe()` function takes a number of parameters that can be used to alter its default behavior in important ways. Here are the default parameters along with a followed by a brief description of each one. 


### RunMe - Default parameters
```python
#in `freemocap/fmc_runme.py`
def RunMe(sessionID=None,
        stage=1,
        useOpenPose=False, 
        runOpenPose = True, 
        useMediaPipe=True,
        runMediaPipe=True,
        useDLC=False,
        dlcConfigPath=None,
        debug=False,
        setDataPath = False,
        userDataPath = None,
        recordVid = True,
        showAnimation = True,
        reconstructionConfidenceThreshold = .7,
        charucoSquareSize = 36, #mm
        calVideoFrameLength = .5,
        startFrame = 0,
        useBlender = True,
        resetBlenderExe = False,
        ):
```

### [RunMe input parameters](#runme-input-parameters)
- `sessionID`
  - Type - (str) 
  - [Default] - None.
  - Identifying string to use for this session. 
  - If creating a new session, default behavior is to autogerate SessionID is based on date and time that the session was recorded
  - If re-processing a previously recorded session, this value specifies which session to reprocess (must be the name of a folder within the `FreeMoCap_Data` folder)
  - 
- `stage`
  - [Type] - Int 
  - [Default] - 1
  - Which processing stage to start from. Processing stages are defined in more detail in [#processing-stages](#processing-stages) 
  
  ```
  stage 1 - Record Raw Videos
  stage 2 - Synchronize Videos
  stage 3 - Camera Calibration
  stage 4 - 2d Tracking and 3d Calibration
  stage 5 - Create output files (using Blender)
  stage 6 - Create output animation (Matplotlib)
  ```  
- `useMediaPipe`
  - [Type] - BOOL
  - [Default] - False, 
  - Whether or not to use the MediaPipe tracking method in `stage=4`

- `runMediaPipe`
  -	[Type] - BOOL
  - [Default] - False, 
  - Whether or not to RUN the MediaPipe tracking method in `stage=4`  (will use previously processed data. This can save a lot of time when re-processing long videos) 
    
- `useOpenPose`
  -	[Type] - BOOL
  - [Default] - False, 
  - Whether or not to use the OpenPose tracking method in `stage=4`

- `runOpenPose`
  -	[Type] - BOOL
  - [Default] - False, 
  - Whether or not to RUN the OpenPose tracking method in `stage=4`  (will use previously processed data. This can save a lot of time when re-processing long videos) 
  
-  `useDeepLabCut`
    - [Type] - BOOL
    - [Default] - False, 
    - Whether or not to use the DeepLabCut model/project specified at `dlcConfigPath`  to track objects in `stage=4`


-  `setDataPath`
	-	[Type] - BOOL
   - [Default] - False, 
   - Trigger the GUI that prompts user to specify location of `FreeMoCap_Data`

-  `userDataPath`
	-	[Type] - BOOL
     - [Default] - False, 
     - path to the location of `FreeMoCap_Data`

-  `recordVid`
	-	[Type] - BOOL
     - [Default] - False, 
     - wehether to save the matplotlib animation to an `.mp4` file

-  `showAnimation`
	-	[Type] - BOOL
     - [Default] - False, 
     - wehether to save the matplotlib animation to an `.mp4` file

- `reconstructionConfidenceThreshold`
  - [Type] - float in range(0,1),
  - [Default] - .7
  - Threshold 'confidence' value to include a point in the 3d reconstruction step
  
- `charucoSquareSize`
  - [Type]  = int
  - [Default] = 36,
  - The size of a side of a black square in the Charuco board used in this calibration. The default value of 36 is approximately appropriate for a print out on an 8" x 10" paper (US Letter, approx A4)
  
- `calVideoLength`
  - [Type]  = int, float in range (0,1), or [int, int]
  - [Default] = .5,
  - What portion of the videos to use in the Anipose calibration step in `stage=3`. `-1` uses the whole recording, a number between 0 and 1 defines a proportion of the video to use, and a tuple of two numbers defines the start and end frame


- `startFrame`
  - [Type]  = int
  - [Default] = 0,
  - what frame of the video to start the animation in `stage=6`

- `useBlender`
  - [Type]  = BOOL
  -  [Default] = True,
  -  Whether to use Blender to create output `.blend`, `.fbx`,`.usd`,and `.gltf` files

- `resetBlenderExe`
  - [Type]  = BOOL
  -  [Default] = False,
  -  Whether to launch GUI to set Blender .exe path (usually something like `C:/Program Files/Blender Foundation/2.95/`)


____
____
## Charuco Board Information
___
  * Our calibration method relies on [Anipose](https://anipose.org)'s [Charuco-based](https://docs.opencv.org/3.4/df/d4a/tutorial_charuco_detection.html) calibration method to determine the location of each camera during a recording session. This information is later used to create the 3d reconstruction of the tracked points

  * IMPORTANT The Charuco board shown to the camera MUST be generated with the `cv2.aruco.DICT_4X4_250` dictionary! 
  
  * Ah high resolution `png` of this Charuco board is in this repository at `/charuco_board_image_highRes.png`
* 
  * To generate your own board, use the following python commands (or equivalent). DO NOT CHANGE THE PARAMETERS OR THE CALIBRATION WILL NOT WORK:
	``` python
	import cv2
	
	aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_250) #note `cv2.aruco` can be installed via `pip install opencv-contrib-python`
	
	board = cv2.aruco.CharucoBoard_create(7, 5, 1, .8, aruco_dict)
	
	charuco_board_image = board.draw((2000,2000)) #`2000` is the resolution of the resulting image. Increase this number if printing a large board (bigger is better! Esp for large spaces!
	
	cv2.imwrite('charuco_board_image.png',charuco_board_image)
	
	```

**Optional**
If you would like to use OpenPose for body tracking, install Cuda and the Windows Portable Demo of OpenPose. 

* Install CUDA: https://developer.nvidia.com/cuda-downloads

* Install OpenPose (Windows Portable Demo): https://github.com/CMU-Perceptual-Computing-Lab/openpose/releases/tag/v1.6.0

* DeepLabCut is also supported, but it's a bit under-tested right now 

Follow the GitHub Repository and/or Join the Discord (https://discord.gg/HX7MTprYsK) for updates!

# Stay Tuned for more soon!


✨💀✨
