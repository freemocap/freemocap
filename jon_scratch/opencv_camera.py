import logging
from typing import List, Optional, Dict
import platform
import time

import numpy as np
import cv2
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MAX_PORTS_TO_CHECK = 20

# class CameraFrame(BaseModel):
#     success: bool
#     image: List
#     timestamp_ns: int #mean of timestamps taken before and after `grab`
#     timestamp: float #timestamp in floating point (seconds), e.g. timestamp_ns / 1e9


class NoCameraAvailableException(Exception):
    pass

class FailedFrameGrabException(Exception):
    pass

# OpenCV Implementation of interacting with a camera
class OpenCVCamera:
    port_number: int=0
    name: str = 'camera0' # `camera{}`.format(port_number)
    exposure: int = -6
    resolution_width: int = 1280
    resolution_height: int = 720

    def connect(self)->bool:
        if platform.system() == 'Windows':
            cap_backend  = cv2.CAP_DSHOW
        else:
            cap_backend  = cv2.CAP_ANY

        logger.info('Starting to look for an available camera')
        success = False

        while not success and self.port_number<MAX_PORTS_TO_CHECK:
            self.port_number+=1
            self.opencv_video_capture_object = cv2.VideoCapture(self.port_number, cap_backend)
            success, image = self.opencv_video_capture_object.read()

            #set camera stream paramters
            self.opencv_video_capture_object.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
            self.opencv_video_capture_object.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution_width)
            self.opencv_video_capture_object.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution_height)

            self.opencv_video_capture_object.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))

        if success:
            logger.error('Camera found at port number {}'.format(self.port_number))
            self.name = 'camera{}'.format(self.port_number)
            return success
        else:
            NoCameraAvailableException()
            logger.error('No camera was available!')
            return success

    def get_next_frame(self)->dict:
        timestamp_ns_pre_grab = time.time_ns()
        grab_success = self.opencv_video_capture_object.grab() #Why grab not read? see -> https://stackoverflow.com/questions/57716962/difference-between-video-capture-read-and-grab
        timestamp_ns_post_grab = time.time_ns()
        timestamp_ns = (timestamp_ns_pre_grab + timestamp_ns_post_grab)/2

        if grab_success:
            success, image =  self.opencv_video_capture_object.retrieve()
            logger.info('{} successfully grabbed a frame at timestamp {}'.format(self.name, timestamp_ns/1e9))
        else:
            FailedFrameGrabException()
            logger.error('{} failed to grab a frame at timestamp {}'.format(timestamp_ns/1e9))

        return success, image, timestamp_ns

    def close(self):
        self.opencv_video_capture_object.release()
        logger.info('Closed camera{}'.format(self.name))


if __name__ == '__main__':
    from rich.console import Console
    console = Console()
    timestamps = []
    try:
        # Test the camera
        camera =  OpenCVCamera()
        camera.connect()

        while True:
            success, image, timestamp_ns = camera.get_next_frame()
            timestamps.append(timestamp_ns/1e9)
            if success:
                mean_fps = 1/np.mean(np.diff(timestamps))
                console.print('{} grabbed a frame at timestamp {} : mean fps = {}'.format(camera.name, timestamp_ns/1e9, mean_fps))
            else:
                console.print('{} failed to grab a frame at timestamp {} : mean fps = {}'.format(camera.name, timestamp_ns/1e9, mean_fps))
            cv2.imshow(camera.name+'- Press ESC to close', image)
            exit_key = cv2.waitKey(1)
            if exit_key ==27:
                break
        cv2.destroyAllWindows()
        camera.close()
    except:
        console.print_exception()





