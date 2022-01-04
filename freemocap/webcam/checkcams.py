from tqdm import tqdm
import cv2
import os
import platform

def TestDevice(source):
    """
    Checks to see if there is a camera available at the input
    """
    if platform.system() == 'Windows':
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(source, cv2.CAP_ANY)
        
    # if cap is None or not cap.isOpened():
    # print('Warning: unable to open video source: ', source)

    if cap.isOpened():
        success, image = cap.read()
        if success:
            # print('Opened: ',source)
            # print('Exposure: '+ str(cap.get(cv2.CAP_PROP_EXPOSURE)))
            # time.sleep(3)
            cap.release()
            cv2.destroyAllWindows()
            open_cam = source
            return open_cam
        else:
            return None
    else:
        return None


def CreateAvailableCamList():
    """
    Loops through the first 20 ports (this number is overkill, really) and creates a list of ports that have a camera available on them 
    """
    openCamList = []
    for x in tqdm(range(20)):  # range 20 right now to be safe
        openCamera = TestDevice(x)
        if openCamera is not None:
            openCamList.append(openCamera)

    return openCamList
