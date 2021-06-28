import threading
import cv2
import time
import pickle


class CamRecordingThread(threading.Thread):
    def __init__(
        self, camID, camInput, videoName, rawVidPath, beginTime, parameterDictionary
    ):
        threading.Thread.__init__(self)
        self.camID = camID
        self.camInput = camInput
        self.videoName = videoName
        self.rawVidPath = rawVidPath
        self.beginTime = beginTime
        self.parameterDictionary = parameterDictionary

    def run(self):
        print("Starting " + self.camID)
        self.timeStamps = CamRecording(
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
    camID, camInput, videoName, rawVidPath, beginTime, parameterDictionary
):
    # the flag is triggered when the user shuts down one webcam to shut down the rest.
    # normally I'd try to avoid global variables, but in this case it's
    # necessary, since each webcam runs as it's own object.
    global flag
    flag = False

    cv2.namedWindow(camID)  # name the preview window for the camera its showing
    cam = cv2.VideoCapture(camInput, cv2.CAP_DSHOW)  # create the video capture object
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
            with open(camID, "wb") as f:
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
            with open(camID, "wb") as f:
                pickle.dump(timeStamps, f)  # dump the data
            break
    cv2.destroyWindow(camID)
    return timeStamps


# this is how we sync our time frames, based on our recorded timestamps
