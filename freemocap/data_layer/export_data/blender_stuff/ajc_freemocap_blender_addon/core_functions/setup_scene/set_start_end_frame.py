import logging

import bpy

logger = logging.getLogger(__name__)


def set_start_end_frame(number_of_frames: int):
    # %% Set start and end frames
    start_frame = 0
    end_frame = number_of_frames
    bpy.context.scene.frame_start = start_frame
    bpy.context.scene.frame_end = end_frame
    logger.info(f"Set start frame to {start_frame} and end frame to {end_frame}")
