from pathlib import Path

import numpy as np
from rich.progress import Progress
import cv2
import mediapipe as mp

# from numba import jit

mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
mp_holistic = mp.solutions.holistic


def run_mediapipe(synched_video_path_list, dummyRun=False):
    """ 
    Run MediaPipe on synced videos, and save body tracking data to be parsed 
    """  
    num_vids = len(synched_video_path_list)
    
    with mp_holistic.Holistic(
                            static_image_mode = False, #use 'static image mode' to avoid system getting 'stuck' on ghost skeletons?
                            model_complexity = 2, #in this house, we turn the Speed/Accuracy dial all the way towards accuracy \o/)
                            ) as holistic:

        mediapipe_results_from_all_videos_list = []  # Create an empty list that holds each cameras data
        each_video_resolution_height = [] # mediapipe gives results in normalized screen coordinate, so we need this to convert to pixels
        each_video_resolution_width = []
        
        for this_vid_path in ( synched_video_path_list):  # Run MediaPipe 'Holistic' (body, hands, face) tracker on each video in the list of synched videos
            mediaPipe_results_from_this_video_list = []  # Create an empty list for mediapipes data
            if not dummyRun:
                cap = cv2.VideoCapture(str(this_vid_path))

                frame_num = -1
                num_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                success, image_raw = cap.read()  # load first image from video

                with Progress() as progress:
                    progressBar = progress.add_task("[magenta]MediaPiping: {}".format(this_vid_path.name),total=num_frames,)  # make progressbar

                    while success:

                        if frame_num % 5 == 0:
                            progress.update( progressBar, advance=5 )  # increment progress bar everyh 5th frame

                        frame_num += 1

                        image_height, image_width, _ = image_raw.shape
                        image = cv2.cvtColor(image_raw, cv2.COLOR_BGR2RGB), #Convert the BGR image to RGB before processing
                        image = image[0] #unpack the tuple into a straight up image
                        results = holistic.process( image)  # NOTE: THIS IS WHERE THE MAGIC HAPENS 

                        mediaPipe_results_from_this_video_list.append( results )  # Append data to mediapipe data list

                        # load the next image (will break `while-loop` on the last frame)
                        success, image_raw = cap.read()  # load next image from video

            each_video_resolution_height.append(image_height)
            each_video_resolution_width.append(image_width)

            mediapipe_results_from_all_videos_list.append( mediaPipe_results_from_this_video_list)  # Append that cameras data for every frame to the camera datalist

    ##  
    ##  
    ##  #Parse MediaPipe into FMC Format
    ##  
    ##  
    
    #standard MediaPipe output
    numBodyPoints = 33
    numFacePoints = 468 #ton of face points because it's a mesh (rather than individually tracked points)
    numHandPoints = 21 #remember, your average person has almost exactly 2 hands

    numTrackedPoints = (numBodyPoints + numHandPoints * 2 + numFacePoints )  # Get total points

    # Create  array of nans the size of number of cams, frame, points, XYC
    mediaPipeData_nCams_nFrames_nImgPts_XYC = np.empty((int(num_vids), int(num_frames), int(numTrackedPoints), 3))  # create empty array
    mediaPipeData_nCams_nFrames_nImgPts_XYC[:] = np.NaN  # Fill it with NaNs!

    list_of_frames_with_full_data = []
    
    for vid_num in range(num_vids):  # Loop through each camera
        this_vid_mediapipe_results_per_frame = mediapipe_results_from_all_videos_list[vid_num]
        for frame_num in range(num_frames):  # Loop through each frame
            
            this_frame_mediapipe_results  = this_vid_mediapipe_results_per_frame[frame_num]
            
            thisFrame_X_body = np.empty(numBodyPoints)
            thisFrame_X_body[:] = np.nan
            thisFrame_Y_body = thisFrame_X_body.copy()
            thisFrame_C_body = thisFrame_X_body.copy() #'C' is for 'condfidence' (mediapipe calls it 'visibility')

            thisFrame_X_face = np.empty(numFacePoints)
            thisFrame_X_face[:] = np.nan
            thisFrame_Y_face = thisFrame_X_face.copy()
            thisFrame_C_face = thisFrame_X_face.copy()

            thisFrame_hands = np.empty(numHandPoints)
            thisFrame_hands[:]= np.nan

            thisFrame_X_lefthand = thisFrame_hands.copy()
            thisFrame_Y_lefthand = thisFrame_hands.copy()
            thisFrame_C_lefthand = thisFrame_hands.copy()

            thisFrame_X_righthand = thisFrame_hands.copy()
            thisFrame_Y_righthand = thisFrame_hands.copy()
            thisFrame_C_righthand = thisFrame_hands.copy()

            fullFrame = True #keep track of which frames have 'full' data (all body, all hands, all face data present)
            try:
                # pull out ThisFrame's mediapipe data (`mpData.pose_landmarks.landmark` returns something iterable ¯\_(ツ)_/¯)
                thisFrame_poseDataLandMarks = this_frame_mediapipe_results.pose_landmarks.landmark  # body ('pose') data
                # stuff body data into pre-allocated nan array
                thisFrame_X_body[:numBodyPoints] = [pp.x for pp in thisFrame_poseDataLandMarks]  # PoseX data - Normalized screen coords (in range [0, 1]) - need multiply by image resultion for pixels
                thisFrame_Y_body[:numBodyPoints] = [pp.y for pp in thisFrame_poseDataLandMarks]  # PoseY data
                thisFrame_C_body[:numBodyPoints] = [pp.visibility for pp in thisFrame_poseDataLandMarks]  #'visibility' is MediaPose's 'confidence' measure in range [0,1]
            except:
                fullFrame = False

            # Right hand data
            try:
                thisFrame_rHandDataLandMarks = this_frame_mediapipe_results.right_hand_landmarks.landmark  # right hand data
                thisFrame_X_righthand[:numHandPoints] = [pp.x for pp in thisFrame_rHandDataLandMarks]  # PoseX data - Normalized screen coords (in range [0, 1]) - need multiply by image resultion for pixels
                thisFrame_Y_righthand[:numHandPoints] = [pp.y for pp in thisFrame_rHandDataLandMarks]  # PoseY data
                thisFrame_C_righthand[:numHandPoints] = [pp.visibility for pp in thisFrame_rHandDataLandMarks]  #'visibility' is MediaPose's 'confidence' measure in range [0,1]
            except:
                fullFrame = False

            # Left hand data
            try:
                thisFrame_lHandDataLandMarks = this_frame_mediapipe_results.left_hand_landmarks.landmark  # left hand data
                thisFrame_X_lefthand[:numHandPoints ] = [pp.x for pp in thisFrame_lHandDataLandMarks]  # PoseX data - Normalized screen coords (in range [0, 1]) - need multiply by image resultion for pixels
                thisFrame_Y_lefthand[:numHandPoints] = [pp.y for pp in thisFrame_lHandDataLandMarks]  # PoseY data
                thisFrame_C_lefthand[:numHandPoints] = [pp.visibility for pp in thisFrame_lHandDataLandMarks]  #'visibility' is MediaPose's 'confidence' measure in range [0,1]
            except:
                fullFrame = False

            # FaceMeshData
            try:
                thisFrame_faceDataLandMarks = this_frame_mediapipe_results.face_landmarks.landmark  # face (mesh) data
                thisFrame_X_face[:numFacePoints] = [pp.x for pp in thisFrame_faceDataLandMarks]  # PoseX data - Normalized screen coords (in range [0, 1]) - need multiply by image resultion for pixels
                thisFrame_Y_face[:numFacePoints] = [pp.y for pp in thisFrame_faceDataLandMarks]  # PoseY data
                # NOTE - There's also Z data in here, but we're gonna ignore it
                thisFrame_C_face[:numFacePoints] = [ pp.visibility for pp in thisFrame_faceDataLandMarks ]  #'visibility' is MediaPose's 'confidence' measure in range [0,1]
            except:
                fullFrame = False

            if fullFrame:
                list_of_frames_with_full_data.append(frame_num)

            thisFrame_X = np.concatenate((thisFrame_X_body,thisFrame_X_righthand,thisFrame_X_lefthand,thisFrame_X_face))
            thisFrame_Y = np.concatenate((thisFrame_Y_body,thisFrame_Y_righthand,thisFrame_Y_lefthand,thisFrame_Y_face))
            thisFrame_C = np.concatenate((thisFrame_C_body,thisFrame_C_righthand,thisFrame_C_lefthand,thisFrame_C_face))
            
            # stuff this frame's data into pre-allocated mediaPipeData_.... array
            mediaPipeData_nCams_nFrames_nImgPts_XYC[vid_num, frame_num, :, 0] = thisFrame_X *each_video_resolution_width[vid_num]# convert from normalized screen coordinates to pixel coordinates
            mediaPipeData_nCams_nFrames_nImgPts_XYC[vid_num, frame_num, :, 1] = thisFrame_Y *each_video_resolution_height[vid_num]
            mediaPipeData_nCams_nFrames_nImgPts_XYC[vid_num, frame_num, :, 2] = thisFrame_C


    mediaPipeData_nCams_nFrames_nImgPts_XYC[:, :, 34:, 2] = 1 #hand and face data don't get 'visibility'/'confidence' scores, so we'll just set them all to 1

    return mediaPipeData_nCams_nFrames_nImgPts_XYC


if __name__ == "__main__":
    synched_vid_folder_path = Path(r"C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2021-12-06_08_52_10_mc\SyncedVideos")
    synched_video_path_list = [vid_path for vid_path in synched_vid_folder_path.glob("*.mp4")]
    
    mediaPipeData_nCams_nFrames_nImgPts_XYC = run_mediapipe(synched_video_path_list=synched_video_path_list)
    mediapipe2d_filename = synched_vid_folder_path.parent/'mediapipe_2d_points.npy'
    np.save(mediapipe2d_filename, mediaPipeData_nCams_nFrames_nImgPts_XYC)
    
    