import logging
import os
import traceback
from typing import List

import cv2

from src.cameras.capture.frame_payload import FramePayload
from src.cameras.persistence.video_writer.save_options import SaveOptions

logger = logging.getLogger(__name__)


class VideoWriter:
    def __init__(self):
        self._frames: List[FramePayload] = []

    @property
    def frame_count(self):
        return len(self._frames)

    def write(self, frame_payload: FramePayload):
        self._frames.append(frame_payload)

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
            logger.info(f"Saved video to path: {options.full_path.resolve()}")
            cv2_writer.release()

    def _create_cv2_video_writer(self, options: SaveOptions):
        return cv2.VideoWriter(
            str(options.full_path.resolve()),
            cv2.VideoWriter_fourcc(*options.fourcc),
            options.fps,
            (options.frame_width, options.frame_height),
        )
