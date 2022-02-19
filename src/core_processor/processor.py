import logging
from typing import Dict, List, NamedTuple

import numpy as np
from aiomultiprocess import Process
from aiomultiprocess.types import Queue

from freemocap.prod.cam.detection.cam_singleton import get_or_create_cams
from jon_scratch.opencv_camera import OpenCVCamera
from src.core_processor.app_events.app_queue import CameraFrameQueue


def create_opencv_cams():
    cams = get_or_create_cams()
    raw_webcam_obj = cams.cams_to_use
    cv_cams = [
        OpenCVCamera(port_number=webcam.port_number)
        for webcam in raw_webcam_obj
    ]
    for cv_cam in cv_cams:
        cv_cam.connect()
    return cv_cams


async def start_camera_capture(queue: Queue):
    processes = []
    creator = CameraCaptureProcess()
    process = Process(
        target=creator.run,
        args=(queue,)
    )
    process.start()
    processes.append(process)


class FramePayload(NamedTuple):
    port_number: int
    image: np.ndarray
    timestamp: int


class ImagePayload(NamedTuple):
    frames: List[FramePayload]


class CameraCaptureProcess:
    async def run(self, queue):
        cv_cams = create_opencv_cams()
        _queue = queue
        _logger = logging.getLogger(__name__)

        while True:
            image_list: List[FramePayload] = []
            for cv_cam in cv_cams:
                success, image, timestamp = cv_cam.get_next_frame()
                
                if not success:
                    continue
                if image is None:
                    continue
                image_list.append(
                    FramePayload(
                        port_number=cv_cam.port_number,
                        image=image,
                        timestamp=timestamp
                    )
                )
            _queue.put(
                ImagePayload(frames=image_list)
            )
            _logger.info("Im printing stuff")
