import threading
import cv2
import imutils


class VideoSetup(threading.Thread):
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
        cap = cv2.VideoCapture(self.camID, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, resWidth)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resHeight)
        cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
        # print('exposure',cap.get(cv2.CAP_PROP_EXPOSURE))
        # if not cap.isOpened():
        #   raise RuntimeError('No camera found at input '+ str(self.camID))
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
    if not cam_inputs:
        raise ValueError("Camera input list (cam_inputs) is empty")

    ulist = []

    for cam_input, cam_rotation in zip(cam_inputs, rotation_input):
        u = VideoSetup(cam_input, paramDict, cam_rotation)
        u.start()
        ulist.append(u)

    for k in ulist:
        k.join()
