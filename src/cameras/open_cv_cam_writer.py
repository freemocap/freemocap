import logging
import os
from pathlib import Path

import cv2

from src.cameras.dtos.create_writer_options import CreateWriterOptions, get_base_options

logger = logging.getLogger(__name__)


class OpenCVCamWriter:
    def create_writer(self, video_capture_obj, options: CreateWriterOptions = None):
        """
        Create writer makes a writer based off a video capture object
        If a write location is specified, then the videos are written there.
        If not, the videos are written to the current working directory

        OS specifics are handled by the Path module.
        """

        if options is None:
            options = get_base_options()
        frame_width = int(video_capture_obj.get(3))
        frame_height = int(video_capture_obj.get(4))
        fps = int(video_capture_obj.get(5))

        final_path = (
            Path()
            .joinpath(os.getcwd(), options.parent_folder, options.filename_and_ext)
            .resolve()
        )
        logger.debug(f"Video save path: {final_path}")
        return cv2.VideoWriter(
            str(final_path),
            cv2.VideoWriter_fourcc(*"MJPG"),
            fps,
            (frame_width, frame_height),
        )

    def close_writer(self, writer: cv2.VideoWriter):
        writer.release()
