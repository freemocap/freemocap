import asyncio

from old_src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from old_src.cameras.detection.cam_singleton import get_or_create_cams
from old_src.cameras.webcam_config import WebcamConfig


async def imshow_testing():
    cams = get_or_create_cams()
    cvcams = []
    for info in cams.cameras_found_list:
        c = OpenCVCamera(WebcamConfig(webcam_id=info.webcam_id))
        c.connect()
        c.start_frame_capture_thread()
        cvcams.append(c)

    await asyncio.gather(*[cam.show() for cam in cvcams])


if __name__ == "__main__":
    asyncio.run(imshow_testing())
