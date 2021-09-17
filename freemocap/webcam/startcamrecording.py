import threading
import cv2
import time
import pickle
import os

class CamRecordingThread(threading.Thread):
    def __init__(
        self, session, camID, camInput, videoName, rawVidPath, beginTime, parameterDictionary
    ):
        threading.Thread.__init__(self)
        self.camID = camID
        self.camInput = camInput
        self.videoName = videoName
        self.rawVidPath = rawVidPath
        self.beginTime = beginTime
        self.parameterDictionary = parameterDictionary
        self.session = session

    def run(self):
        print("Starting " + self.camID)
        self.timeStamps = CamRecording(
            self.session,
            self.camID,
            self.camInput,
            self.videoName,
            self.rawVidPath,
            self.beginTime,
            self.parameterDictionary,
        )

    def getStamps(self):
        return self.timeStamps


# the recording function that each threaded camera object runs
def CamRecording(
    session, camID, camInput, videoName, rawVidPath, beginTime, parameterDictionary
):
    """
    Runs the recording process for each threaded camera instance. Saves a video to the RawVideos folder.
    Saves a timestamp for each frame into a pickle file. Checks for whether the global variable 'flag' 
    has been set to True to end the recording (the first camera to end sets the flag to True, which
    means the rest of the cameras will quit in short order)
    """
    # the flag is triggered when the user shuts down one webcam to shut down the rest.
    # normally I'd try to avoid global variables, but in this case it's
    # necessary, since each webcam runs as it's own object.
    global flag
    flag = False

    cv2.namedWindow(camID)  # name the preview window for the camera its showing

    if os.name == 'nt': #use CAP_DSHOW for windows, CAP_ANY otherwise (*might* make things ubuntu/mac compatible, but not sure. See https://github.com/jonmatthis/freemocap/issues/52)
        cam = cv2.VideoCapture(camInput, cv2.CAP_DSHOW)
    else:
        cam = cv2.VideoCapture(camInput, cv2.CAP_ANY)


    # if not cam.isOpened():
    #         raise RuntimeError('No camera found at input '+ str(camID))
    # pulling out all the dictionary paramters
    exposure = parameterDictionary.get("exposure")
    resWidth = parameterDictionary.get("resWidth")
    resHeight = parameterDictionary.get("resHeight")
    framerate = parameterDictionary.get("framerate")
    codec = parameterDictionary.get("codec")


  

    cam.set(cv2.CAP_PROP_FRAME_WIDTH, resWidth)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, resHeight)
    cam.set(cv2.CAP_PROP_EXPOSURE, exposure)
    fourcc = cv2.VideoWriter_fourcc(*codec)
    # rawPath = filepath/'RawVideos' #creating a RawVideos folder
    # rawPath.mkdir(parents = True, exist_ok = True)
    width = cam.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cam.get(cv2.CAP_PROP_FRAME_HEIGHT)
    print("width:", width, "height:", height)
    saveRawVidPath = str(
        rawVidPath / videoName
    )  # create a save path for each video to the RawVideos folders
    out = cv2.VideoWriter(saveRawVidPath, fourcc, framerate, (resWidth, resHeight))
    timeStamps = []  # holds the timestamps

    if cam.isOpened():
        success, frame = cam.read()
    else:
        success = False

    while (
        success
    ):  # while the camera is opened, record the data until the escape button is hit
        if flag:  # when the flag is triggered, stop recording and dump the data
            with open(session.rawVidPath/camID, "wb") as f:
                pickle.dump(timeStamps, f)
            break
        success, frame = cam.read()

        cv2.imshow(camID, frame)
        frame_sized = cv2.resize(frame, (resWidth, resHeight))
        # frame_sized = frame
        out.write(frame_sized)
        timeStamps.append(time.time() - beginTime)  # add each timestamp to the list

        key = cv2.waitKey(20)
        if key == 27:  # exit on ESC
            flag = True  # set flag to true to shut down all other webcams
            with open(session.rawVidPath/camID, "wb") as f:
                pickle.dump(timeStamps, f)  # dump the data
            break
    cv2.destroyWindow(camID)
    return timeStamps


# this is how we sync our time frames, based on our recorded timestamps
