from aiomultiprocess import Process
from orjson import orjson

from freemocap.prod.cam.detection.cam_singleton import get_or_create_cams
from jon_scratch.opencv_camera import OpenCVCamera


def create_opencv_cams():
    cams = get_or_create_cams()
    webcam_ids = cams.cams_to_use
    cv_cams = [
        OpenCVCamera(port_number=webcam.port_number)
        for webcam in webcam_ids
    ]
    for cv_cam in cv_cams:
        cv_cam.connect()
    return cv_cams


async def open_process(queue):
    p = Process(target=start_processing, args=(queue,))
    p.start()
    await p.join()


async def open_board_detection_process(queue):
    p = Process(target=start_processing, args=(queue,))
    p.start()
    await p.join()


async def start_processing(queue):
    cv_cams = create_opencv_cams()
    while True:
        for cv_cam in cv_cams:
            success, image, timestamp = cv_cam.get_next_frame()
            if not success:
                continue
            if image is None:
                continue
            d = {
                "frameData": str(image.tobytes()),
                "timestamp": timestamp,
            }
            d = orjson.dumps(d)
            queue.put_nowait(d)
