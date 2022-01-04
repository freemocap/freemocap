from rich.progress import track
import cv2
import imutils
import numpy as np
import os


def VideoTrim(session, vidList, ft, parameterDictionary, rotationState, numCamRange):
    """ 
    From the list of saved frames from the time-syncing function, create synced videos by pulling those specific 
    frames from the original raw videos into new videos, replacing any duplicate frames with a black 'buffer' slide
    """  
    camList = list(
        ft.columns[1 : len(vidList) + 1]
    )  # grab the camera identifiers from the data frame
    resWidth = parameterDictionary.get("resWidth")
    resHeight = parameterDictionary.get("resHeight")
    framerate = parameterDictionary.get("framerate")
    trueWidth = resWidth  # creating true resWidth and resHeight in case we need to rotate our images
    trueHeight = resHeight
    codec = parameterDictionary.get("codec")
    postTrimmingTotalNumFrames = []

    for vid,cam,camNum in zip(vidList,camList,numCamRange): #iterate in parallel through camera identifiers and matching videos
        this_vid_path = session.rawVidPath/vid
        print('synchronizing video at - ' + str(this_vid_path))
        cap = cv2.VideoCapture(str(this_vid_path)) #initialize OpenCV capture
        frameTable = ft[cam] #grab the frames needed for that camera
        success, image = cap.read() #start reading frames
        fourcc = cv2.VideoWriter_fourcc(*codec)
        saveName = session.sessionID + "_synced_" + cam + ".mp4"

        saveSyncedVidPath = str(
            session.syncedVidPath / saveName
        )  # create an output path for the function
        if rotationState[camNum] == 90 or rotationState[camNum] == 270:
            # if we are rotating to these angles, we need to temporarily swap our resWidth and resHeight
            tempHeight = resHeight
            resHeight = resWidth
            resWidth = tempHeight

        out = cv2.VideoWriter(
            saveSyncedVidPath, fourcc, framerate, (resWidth, resHeight)
        )  # change resolution as needed
        count = 0
        for frame in track(frameTable):  # start looking through the frames we need
            if frame == -1:  # this is a buffer frame
                blankFrame = np.zeros_like(image)  # create a blank frame
                if rotationState[camNum] is not None:
                    blankFrame = imutils.rotate_bound(
                        blankFrame, angle=rotationState[camNum]
                    )
                    blankFrame = cv2.resize(blankFrame, (resWidth, resHeight))
                out.write(blankFrame)  # write that frame to the video
                count += 1
            else:
                cap.set(
                    cv2.CAP_PROP_POS_FRAMES, frame
                )  # set the video to the frame that we need
                success, image = cap.read()
                if rotationState[camNum] is not None:
                    image = imutils.rotate_bound(image, angle=rotationState[camNum])
                    image = cv2.resize(image, (resWidth, resHeight))
                out.write(image)
                f = 2
            
        resWidth = trueWidth
        resHeight = trueHeight
        cap.release()
        out.release()
        frame_length_cap = cv2.VideoCapture(saveSyncedVidPath)
        thisCamNumFrame = int(frame_length_cap.get(cv2.CAP_PROP_FRAME_COUNT)) 
        postTrimmingTotalNumFrames.append(thisCamNumFrame)
        print('Saved '+ saveSyncedVidPath)
        print()

    assert postTrimmingTotalNumFrames.count(postTrimmingTotalNumFrames[0]) == len(postTrimmingTotalNumFrames), "Number of frames in each synced video is not the same"
    session.postTrimmingNumFrames = postTrimmingTotalNumFrames[0]
    session.numFrames = postTrimmingTotalNumFrames[0]


def createCalibrationVideos(session,calVideoFrameLength,parameterDictionary):

    vidList = os.listdir(session.syncedVidPath)
    framelist = list(range(calVideoFrameLength))
    codec = parameterDictionary.get("codec")
    for count, vid in enumerate(vidList, start=1):
        cam_name = "Cam{}".format(count)
        cap = cv2.VideoCapture(str(session.syncedVidPath / vid))
        fourcc = cv2.VideoWriter_fourcc(*codec)

        # grab resolution parameters from the videos
        resWidth = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        resHeight = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        framerate = int(cap.get(cv2.CAP_PROP_FPS))

        saveName = (
            session.sessionID + "_trimmed_" + cam_name + ".mp4"
        )  # create a name for the trimmed video
        saveCalVidPath = str(
            session.calVidPath / saveName
        )  # create an output path for the function

        success, image = cap.read()  # start reading frames

        out = cv2.VideoWriter(saveCalVidPath, fourcc, framerate, (resWidth, resHeight))
        print("Trimming " + cam_name)
        for frame in track(framelist):
            cap.set(
                cv2.CAP_PROP_POS_FRAMES, frame
            )  # set the video to the frame that we need
            success, image = cap.read()
            out.write(image)
    cap.release()
    out.release()
