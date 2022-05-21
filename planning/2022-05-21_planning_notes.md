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
       
       - 







1 - Calibrate
    - detect charuco boards in syncrhonized images from cameras and when you have enough, send it to anipose and get 
        back the camera calibration info (saved to a toml by anipose)

2 - Run-time - record videos/track skeletons/3d reconstruction
    - do as good as your computer allows and divert raw images away from core pipeline for later offline processing

3 - Off-line processing 
    - same as (2) but using previously (or externally )recorded videoes, to be processed at 'max accuracy, fuck speed' mode

4 - post-processing and analysis
    - do stuff with data output from 3 and/or 4


## Questions for those Pyuvc people - Pupil Labs

1. What is a good, robust way to detect cameras on a system regardless of Operating System?
2. Also, whats a good way to get unique identifiers for camera devices regardless of Operating System?
3. Whats a good way to retrieve camera data for N number of cameras without incurring steep processing penalties? (Threading, Multiprocessing, other techniques?)