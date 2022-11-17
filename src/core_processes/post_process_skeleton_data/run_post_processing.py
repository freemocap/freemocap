import logging
import sys
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd
from rich.progress import track
from scipy import signal

from src.core_processes.post_process_skeleton_data.post_processing_functions import filter_data, gap_fill_data, \
    rotate_skeleton, find_good_frame
from src.core_processes.post_process_skeleton_data.reference_files.landmark_names import mediapipe_landmark_names

logger = logging.getLogger(__name__)


def gap_fill_and_filter_data(
        skel3d_frame_marker_xyz: np.ndarray,
        sampling_rate: Union[float, int],
        cut_off: Union[float, int],
        order: Union[float, int],
):
    logger.info("Gap-filling data...")

    skel3d_data_gap_filled = gap_fill_data.gap_fill_freemocap_data(
        skel3d_frame_marker_xyz,
    )

    logger.info('Filtering data...')

    skel_3d_data_filtered = filter_data.butterworth_filter_skeleton(
        skel3d_data_gap_filled,
        cut_off,
        sampling_rate,
        order,
    )

    return skel_3d_data_filtered


def origin_align_skeleton(
    skel3d_frame_marker_xyz: np.ndarray,
    reference_frame_number=None,
):
    logger.info('Finding reference frame for alignment...')

    if not reference_frame_number:
        reference_frame_number = find_good_frame.find_good_frame_recursive_guess_method(
            skel3d_frame_marker_xyz,
            mediapipe_landmark_names,
            initial_velocity_guess=.3,
        )

    origin_aligned_skeleton_data = rotate_skeleton.align_skeleton_with_origin(
        skel3d_frame_marker_xyz,
        mediapipe_landmark_names,
        reference_frame_number,
    )[0]

    return origin_aligned_skeleton_data

