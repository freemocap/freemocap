# Function Details

## Roboflow Folder

All scripts in this folder are taken directly from the roboflow repoisitory. The only script
that I made changes to was *roboflow_yolo.py* , specifically the function *run_roboflow*

### Run_Roboflow

Function has many inputs, most importantly *weights* which is the yolo model that is being used 
where the fastest and least accurate model is yolov5s.pt and the slowest but most accurate model is
yolov5x.pt. The other input of importance is *input_video* which is the video that gets analyzed by 
yolo and roboflow. Generally, the other inputs can stay as their defaults. This function then utilizes
all the functionality from the roboflow repository and runs the video through yolo and roboflow to 
output a dictionary that which has keys of each person in the video and the value of the key is a 
dataframe of containing the bounding box of each person in the order 'frame','xmin','ymin',xmax','ymax'

## fmc_mediapipe_roboflow.py

### runRoboflowAndMediapipe

This is the main function of the *fmc_mediapipe_roboflow.py* script. Takes the session class as input and 
then loops through each video in the session to run them through yolo and then through mediapipe. Has logic
for multi person detection but has not been tested yet, only has funcitoned correctly with single person. 
Saves out an numpy array in the shape nCams_nFrames_nImgPts_XYC and also returns this array.

### mediapipe_on_roboflow_crop

Function takes in input video and the corresponding dictionary containing the coordinates of the bounding boxes 
of each person in the video. Each frame of the video is looped through and cropped to the coordiates of the bounding 
box and then runs them through mediapipe. Outputs a dictionary of the mediapipe data.

*Note: There is logic for multi person detection where the output dictionary has keys that represent each person in the video
and the value of the keys is the mediapipe data for that person throughout the entire video. However, there was some bugs in this
logic, so currently the script just takes the first person detected in each frame and saves that person out. If there is no one 
in the frame, nan data is stored for that frame. This works for single person but if there is multiple people in frame there will
need to be tweaking of this function.*

### multi_person_sorting

*Needs more testing* Function takes in the mediapipe dictionaries from each camera view and the camera view with most people
in it as an input. Using a comparison of the derivative of the position of the people in camera view it assigns a number to each
person that is consistent across all camera views. Returns a dictionary in the same format as input, except the number assigned 
to each person is consistent in all views

### derive_position_array
Takes in mediapipe data and derives it to retuen a derivative of mediapipe data

### check_for_calculator_error_frame
Input is the name of the video currently being processed. The function loads in a json file that contains a list of 
videos and the corresponding frames where a calcualtor error occurs. If the input video name is on the list, the frame 
where there is a calculator error is returned. That frame number is then skipped in the mediapipe processing. 

### add_Nan_frame
Returns a nan array in the shape of a frame of mediapipe data. Used when there is no one in frame

### get_mediapipe_keypoint_numbers
Outputs the amount of body, hands, and face points and the sum of all these points


### format_mediapipe_for_fmc

Takes mediapipe results, image_height and image_width as an input and reshapes the mediaipipe data into the freemocap format


