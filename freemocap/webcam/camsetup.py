import threading
import cv2
import imutils
import os


class VideoSetup(threading.Thread):
    """
    Class to run and thread webcams for preview purposes
    """
    def __init__(self, camID, parameterDictionary, rotNum):
        self.camID = camID
        self.parameterDictionary = parameterDictionary
        self.rotNum = rotNum
        threading.Thread.__init__(self)

    def run(self):
        # print("Starting " + self.previewName)
        self.record(self.parameterDictionary, self.rotNum)

    def record(self, parameterDictionary, rotNum):
        exposure = parameterDictionary.get("exposure")
        resWidth = parameterDictionary.get("resWidth")
        resHeight = parameterDictionary.get("resHeight")
        camName = "Camera" + str(self.camID)

        cv2.namedWindow(camName)

        if os.name == 'nt': #use CAP_DSHOW for windows, CAP_ANY otherwise (*might* make things ubuntu/mac compatible, but not sure. See https://github.com/jonmatthis/freemocap/issues/52)
            cap = cv2.VideoCapture(self.camID, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(self.camID, cv2.CAP_ANY)

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, resWidth)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resHeight)
        cap.set(cv2.CAP_PROP_EXPOSURE, exposure)

            # showing values of the properties
        print("__________________________________________")
        print("cv2::videocapture properties for Camera# {}".format(self.camID))
        print("CV_CAP_PROP_FRAME_WIDTH: '{}'".format(cap.get(cv2.CAP_PROP_FRAME_WIDTH)))
        print("CV_CAP_PROP_FRAME_HEIGHT : '{}'".format(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        print("CAP_PROP_FPS : '{}'".format(cap.get(cv2.CAP_PROP_FPS)))
        print("CAP_PROP_EXPOSURE : '{}'".format(cap.get(cv2.CAP_PROP_EXPOSURE)))
        print("CAP_PROP_POS_MSEC : '{}'".format(cap.get(cv2.CAP_PROP_POS_MSEC)))
        print("CAP_PROP_FRAME_COUNT  : '{}'".format(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        print("CAP_PROP_BRIGHTNESS : '{}'".format(cap.get(cv2.CAP_PROP_BRIGHTNESS)))
        print("CAP_PROP_CONTRAST : '{}'".format(cap.get(cv2.CAP_PROP_CONTRAST)))
        print("CAP_PROP_SATURATION : '{}'".format(cap.get(cv2.CAP_PROP_SATURATION)))
        print("CAP_PROP_HUE : '{}'".format(cap.get(cv2.CAP_PROP_HUE)))
        print("CAP_PROP_GAIN  : '{}'".format(cap.get(cv2.CAP_PROP_GAIN)))
        print("CAP_PROP_CONVERT_RGB : '{}'".format(cap.get(cv2.CAP_PROP_CONVERT_RGB)))
        print("__________________________________________")

        while True:
            ret1, frame1 = cap.read()
            if ret1 == True:
                if rotNum is not None:
                    frame1 = imutils.rotate_bound(frame1, angle=rotNum)
                cv2.imshow(camName, frame1)
                if cv2.waitKey(1) & 0xFF == 27:
                    # == ord('q') for q
                    break

            else:
                break
        cv2.destroyWindow(camName)


def RunSetup(cam_inputs, rotation_input, paramDict):
    """
    Start video setup by threading instances of the VideoSetup class
    """
    if not cam_inputs:
        raise ValueError("Camera input list (cam_inputs) is empty")

    ulist = []

    for cam_input, cam_rotation in zip(cam_inputs, rotation_input):
        u = VideoSetup(cam_input, paramDict, cam_rotation)
        u.start()
        ulist.append(u)

    for k in ulist:
        k.join()
