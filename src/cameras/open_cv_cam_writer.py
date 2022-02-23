import os
import time
from pathlib import Path

import cv2


class OpenCVCamWriter:
    def create_writer(self, video_capture_obj):
        frame_width = int(video_capture_obj.get(3))
        frame_height = int(video_capture_obj.get(4))
        fps = int(video_capture_obj.get(5))
        timestr = time.strftime("%Y%m%d_%H%M%S")
        p = Path().joinpath(os.getcwd(), f"{timestr}.avi").resolve()
        return cv2.VideoWriter(
            "outfile.avi",
            cv2.VideoWriter_fourcc("M", "J", "P", "G"),
            fps,
            (frame_width, frame_height),
        )
