from pathlib import Path
from typing import Union

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal


import logging

from src.core_processes.post_process_skeleton_data.gap_fill_filter_and_origin_align_skeleton_data import (
    gap_fill_filter_origin_align_3d_data_and_then_calculate_center_of_mass,
)

logger = logging.getLogger(__name__)


class PostProcess3dDataThreadWorker(QThread):
    finished = pyqtSignal(str)

    def __init__(
        self,
        skel3d_frame_marker_xyz: np.ndarray,
        skeleton_reprojection_error_fr_mar: np.ndarray,
        data_save_path: Union[str, Path],
        sampling_rate: int,
        cut_off: float,
        order: int,
        reference_frame_number: int = None,
    ):
        super().__init__()
        self.skel3d_frame_marker_xyz = skel3d_frame_marker_xyz
        self.skeleton_reprojection_error_fr_mar = skeleton_reprojection_error_fr_mar
        self.data_save_path = data_save_path
        self.sample_rate = sampling_rate
        self.cut_off = cut_off
        self.order = order
        self.reference_frame_number = reference_frame_number

    def run(self):
        gap_fill_filter_origin_align_3d_data_and_then_calculate_center_of_mass(
            self.skel3d_frame_marker_xyz,
            skeleton_reprojection_error_fr_mar=self.skeleton_reprojection_error_fr_mar,
            path_to_folder_where_we_will_save_this_data=self.data_save_path,
            sampling_rate=self.sample_rate,
            cut_off=self.cut_off,
            order=self.order,
            reference_frame_number=self.reference_frame_number,
        )
        self.finished.emit("Done!")
