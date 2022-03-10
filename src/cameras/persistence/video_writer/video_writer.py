import logging
import os
import traceback
from pathlib import Path
from typing import List, Optional

import cv2
from pydantic import BaseModel

from src.cameras.capture.frame_payload import FramePayload
from src.cameras.capture.opencv_camera.opencv_camera import OpenCVCamera
from src.config.data_paths import create_path

logger = logging.getLogger(__name__)


class SaveOptions(BaseModel):
    writer_dir: Path
    filename: str = "movie.mp4"
    fps: float
    fourcc: str = "MP4V"
    frame_width: int
    frame_height: int
    cv_cam: Optional[OpenCVCamera]

    @property
    def full_path(self):
        return Path().joinpath(self.writer_dir, self.filename)


class VideoWriter:
    def __init__(self):
        self._frames: List[FramePayload] = []

    @property
    def frame_count(self):
        return len(self._frames)

    def write(self, frame_payload: FramePayload):
        self._frames.append(frame_payload)

    def save_by_cam(self, cv_cam: OpenCVCamera, fps: float):
        options = SaveOptions(
            writer_dir=create_path(
                cv_cam.session_writer_base_path,
                "board_detection",
                f"webcam_{cv_cam.webcam_id_as_str}",
            ),
            fps=fps,
            frame_width=cv_cam.get_frame_width(),
            frame_height=cv_cam.get_frame_height(),
        )

        self.save(options)

    def save(self, options: SaveOptions):
        if not os.path.exists(options.writer_dir):
            os.makedirs(options.writer_dir.resolve())

        cv2_writer = self._create_cv2_video_writer(options)
        try:
            for frame in self._frames:
                cv2_writer.write(frame.image)
        except:
            logger.debug("Failed during save in video writer")
            traceback.print_exc()
        finally:
            cv2_writer.release()

    def _create_cv2_video_writer(self, options: SaveOptions):
        return cv2.VideoWriter(
            str(options.full_path.resolve()),
            cv2.VideoWriter_fourcc(*options.fourcc),
            options.fps,
            (options.frame_width, options.frame_height),
        )
