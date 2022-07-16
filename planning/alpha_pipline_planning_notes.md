# five standard states/tasks of/for the software

0 - Setup and preview
    - preview camera views
    - set parameters future recordings and not

 - parameters to configure
   - for a given recording session, we need to know -
     ## session settings
     - base `freemocap data folder` 
     - `session ID` (will become a new folder in the base data folder)
     ## calibration settings
     - `record_new_calibration?` - bool
     - `load_previous_calibration?` - bool
     - `calibrate_in_recording?` - bool 
   - 
     ## how to process the data in realtime 
       - which tracking algorithms to apply to the data
         ### mediapipe settings
           - model_complexity
           - min_threshold_to_track_skeleton
             - min_threshold_to_reconstruct 
         ### maybe some deeplabcut stuff in the future
          - path to config yaml
         ### 3d reconstuction settings
         - `reconstruction_threshold`
         
     ## camera settings
         - webcam_id:int=0
         - exposure: int = -6
         - resolution_width: int = 800
         - resolution_height: int = 600
         - save_video: bool = True
         - fourcc: str = "MJPG"
         - rotate_image: None, 90, 180, 270 #how much to rotate the image
       
       - 







# 1 - Calibrate
Detect charuco boards in syncrhonized images from each camera and then send to `aniposelib` to get camera calibration. 

Results in a `[session_id]_calibration.toml` file saved to `session_folder` that can be used to estimate 3d points from synchronized 2d views

We might also want to save this `calibration.toml` somewhere under the name `previous_calibration.toml` that can be used as a default if no other calibration file is selected (i.e. so that folks can calibrate once and then record a number of sessions in a row, assuming that the cameras dont move between sessions. We can also check `reprojection_error` and throw a warning when the errors suggest that the system needs recalibrating)

#### Notes

uses `aniposelib` methods, or possibly the slightly tweaked versions in `freemocap/fmc_anipose`. We'll eventually want to alter these methods to better fit our needs (I talked to the original creator and he's super into the idea, and is happy to lend help when he can (but he's distracted writing his dissertation for the next few months))

#### Potential Workflow(s) -
- NOTE - this workflow assumes a distinct separation between `calibration` and `recording,` 
  - that is, the user clicks "start calibrate" button, does calibration stuff, clicks "end calibration" button (or it auto-ends)
  - We could integrate this into the `record session` behavior, but that might be a bit more complicated?
- Calibration steps 
  1. **User** - clicks "Start Calibration"
	  - starts `recording` videos from each camera
  2. **User** - shows charucoboard to each camera, trying to get overlapping, shared views of the full board between the different cameras
	  - We'll need instructions of some kind to help Users calibrate
	  - Some nice visualizations on the screen will go along way
  3. **Code** - Keep track of 'shared views' for each camera
		  - i.e. frames on which (say) `camera 1` and `camera 2` both have both detected the full charuco board would lead us to increment the `shared_full_board_views` for `Camera1` and `Camera2` by `+1`
	4. **Code** -  when you have enough shared views (i.e. each camera has at least `100` shared `shared_full_board_views`, send end the recorded videos to `aniposelib`
		  - We might be able to send it as a bunch of `numpy` arrays, but I think default `anipose` might require them to be saved as `mp4` files first. That's annoying, but we can fix/upgrade that later
		  - `aniposelib` will produce:
			- PRIMARY OUTPUT 
				  - `[session_id]_calibration.toml` containing camera calibration info
					  - save to `session_folder` & internally under the name `previous_calibration.toml` (see above)
			  - SECONDARY OUTPUT 
				  - `2D` and `3D` data from `charuco_board`
				  - `reprojection_error` of detected boards
					  - Can be used to do a `health/quality` check of the calibration


# 2 - Run-time processing
This is what happens when the User presses "Record" or whatever. 
Pre-reqs: 
 - Connection to synchronized cameras that can produce `multi_image_payload` on demand in a `while recording == True:` kind of loop:
	 - `multi_frame_payload`:  a `tuple` or `Class` of `frame_payload` objects
		 - one from each camera (or an `empty` one if there's a frame drop)
		 - verified to have `timestamps` within +/- `frame_interval` (or +/- `frame_interval/2`?) of each other
 - a `calibration.toml` as produced by the `Calibration` step
 
#### Top priority- Record videos 
- Record synchronized videos from all cameras
	- minimize frame drops
	- must not lose data if there's a crash 
	- must be able to re-process previously recorded videos
		- OpenCV makes this easy, as the`cv2.VideoCapture` object treats videos, USB cameras, and IP cameras equivalently
- Results in the same number of saved video files as there are cameras
	- each video has *precisely* the same number of frames (and those frames are synchronized
	- save as `mp4` (which are easist to work with, but can't be read if there's a crash)
	- or maybe `mkv` (harder to work with, but remain viable if there is a crash)
	- maybe save as `mkv` and convert to `mp4`?

#### Secondary Priority- Track 2d skeletons and generate 3d  skels for real-time interactive visualization and applications (e.g. VR and whatnot)
- For each incoming `multi_frame_payload`, process each image with `mediapipe.holistic` (in the `detect_skeletons` functionality) to estimate the `2d_skeleton`
- once you've got a skeleton for each camera's view, combine with `calibration.toml`to  get a `3D_skeleton` estimate
- Send that `3D_skeleton` data to whatever is running the `visualization` (PyQt/OpenGL, Three.JS, Blender, etc)
- NOTE 
	- The `2d_skeleton` tracking is computationally expensive, so this part will be limited by the power of the PC that's running to recording
		- powerful enough computers may be able to reconstruct `3d_skeletons` fast enough to generate a visualization that matches the `framerate` of the camera
		- weaker computers can either:
			- Skip frames, so the framerate of the 3d visualization will be less than the cameras
			- Process all frames, so the 3d visualization is lagged vs real-time
			- decrease `model_complexity` or down-res incoming images to speed up processing
				- (but still save the full-res images to `video_files`)
		- If we can run this on `GPU` it might massively increase performance
	- 



# 3 - Off-line processing 
- same as (2) but using previously (or externally )recorded videoes, to be processed at 'max accuracy, fuck speed' mode.
- Basically, you do the best you can during run time, but you make sure to save all the videos at full-fps and full-resolution so that you can go back later and re-process them with as high of accuracy as possible.

# 4 - post-processing and analysis
- do stuff with data output from 3 and/or 4. This'll mostly dumping the 2D and 3D data from sections `2` and/or `3` into `pandas.dataframe >> csv` or various format for later processing
- I'll probably want to build some basic post-processing clean-up and analysis capacity to this system, but we can cross that bridge when we get to it. 
 

## Questions for those Pyuvc people - Pupil Labs

1. What is a good, robust way to detect cameras on a system regardless of Operating System?
2. Also, whats a good way to get unique identifiers for camera devices regardless of Operating System?
3. Whats a good way to retrieve camera data for N number of cameras without incurring steep processing penalties? (Threading, Multiprocessing, other techniques?)