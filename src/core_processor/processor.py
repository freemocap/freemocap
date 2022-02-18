import logging
import time

from aiomultiprocess import Process
from orjson import orjson

from freemocap.prod.cam.detection.cam_singleton import get_or_create_cams
from jon_scratch.opencv_camera import OpenCVCamera


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


async def capture_cam_images_new_process(queue):
    p = Process(target=_start_camera_capture, args=(queue,))
    p.start()
    await p.join()


async def _start_camera_capture(queue):
    cv_cams = create_opencv_cams()
    logger = logging.getLogger(__name__)
    # threading could be added here!
    while True:
        for cv_cam in cv_cams:
            t1_start = time.perf_counter()
            success, image, timestamp = cv_cam.get_next_frame()
            if not success:
                continue
            if image is None:
                continue
            # Whats the performance difference between tuple queue passing vs dict
            d = {
                "image": image,
                "timestamp": timestamp,
            }
            d = orjson.dumps(d)
            queue.put_nowait(d)
            t1_stop = time.perf_counter()
            logger.info(f"Elapsed time per insert into queue: {t1_stop - t1_start}")

