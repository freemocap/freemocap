from pathlib import Path
from typing import Dict, Union, Callable

import numpy as np
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget
from src.cameras.detection.models import FoundCamerasResponse
from src.cameras.persistence.video_writer.video_recorder import VideoRecorder

from src.gui.main.workers.anipose_calibration_thread_worker import (
    AniposeCalibrationThreadWorker,
)
from src.gui.main.workers.cam_detection_thread_worker import CameraDetectionThreadWorker

import logging

from src.gui.main.workers.export_to_blender_worker import ExportToBlenderThreadWorker
from src.gui.main.workers.mediapipe_2d_detection_thread_worker import (
    Mediapipe2dDetectionThreadWorker,
)
from src.gui.main.workers.save_to_video_thread_worker import SaveToVideoThreadWorker
from src.gui.main.workers.triangulate_3d_data_thread_worker import (
    Triangulate3dDataThreadWorker,
)

logger = logging.getLogger(__name__)


class ThreadWorkerManager(QWidget):
    """This guy's job is to hold on to the parts of threads that need to be kept alive while they are running"""

    camera_detection_finished = pyqtSignal(FoundCamerasResponse)
    videos_saved_signal = pyqtSignal(bool)
    start_3d_processing_signal = pyqtSignal()
    start_blender_processing_signal = pyqtSignal()
    blender_file_created_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()

    def launch_detect_cameras_worker(self):
        logger.info("Launching `Camera Detection` thread worker")
        self._camera_detection_thread_worker = CameraDetectionThreadWorker()
        self._camera_detection_thread_worker.finished.connect(
            self.camera_detection_finished.emit
        )
        self._camera_detection_thread_worker.start()

    def launch_save_videos_thread_worker(
        self,
        folder_to_save_videos: Union[str, Path],
        dictionary_of_video_recorders: Dict[str, VideoRecorder],
        calibration_videos: bool = False,
    ):
        logger.info("Launching `Save Videos` thread worker...")

        self._save_to_video_thread_worker = SaveToVideoThreadWorker(
            dictionary_of_video_recorders=dictionary_of_video_recorders,
            folder_to_save_videos=folder_to_save_videos,
        )
        self._save_to_video_thread_worker.start()
        self._save_to_video_thread_worker.finished.connect(
            lambda: self.videos_saved_signal.emit(calibration_videos)
        )

    def launch_anipose_calibration_thread_worker(
        self,
        calibration_videos_folder_path: Union[str, Path],
        charuco_square_size_mm: float,
        session_id: str,
        jupyter_console_print_function_callable: Callable,
    ):
        logger.info("Launching `Anipose (Charuco Board) Calibration` thread worker")
        self._anipose_calibration_worker = AniposeCalibrationThreadWorker(
            calibration_videos_folder_path=calibration_videos_folder_path,
            charuco_square_size_mm=charuco_square_size_mm,
            session_id=session_id,
        )
        self._anipose_calibration_worker.start()
        self._anipose_calibration_worker.in_progress.connect(
            jupyter_console_print_function_callable
        )

    def launch_detect_2d_skeletons_thread_worker(
        self,
        synchronized_videos_folder_path: Union[str, Path],
        output_data_folder_path: Union[str, Path],
        auto_process_next_stage: bool = True,
    ):
        logger.info("Launching `Detect Mediapipe 2d Skeleton` thread worker...")

        self._mediapipe_2d_detection_thread_worker = Mediapipe2dDetectionThreadWorker(
            path_to_folder_of_videos_to_process=synchronized_videos_folder_path,
            output_data_folder_path=output_data_folder_path,
        )

        if auto_process_next_stage:
            self._mediapipe_2d_detection_thread_worker.finished.connect(
                self.start_3d_processing_signal.emit
            )
        self._mediapipe_2d_detection_thread_worker.start()

    def launch_triangulate_3d_data_thread_worker(
        self,
        anipose_calibration_object,
        mediapipe_2d_data: np.ndarray,
        output_data_folder_path: Union[str, Path],
        mediapipe_confidence_cutoff_threshold: float = 0.0,
        auto_process_next_stage: bool = False,
    ):
        logger.info("Launching `Triangulate 3d Data` thread worker...")

        self._triangulate_3d_data_thread_worker = Triangulate3dDataThreadWorker(
            anipose_calibration_object=anipose_calibration_object,
            mediapipe_2d_data=mediapipe_2d_data,
            output_data_folder_path=output_data_folder_path,
            mediapipe_confidence_cutoff_threshold=mediapipe_confidence_cutoff_threshold,
        )

        self._triangulate_3d_data_thread_worker.start()

        if auto_process_next_stage:
            self._triangulate_3d_data_thread_worker.finished.connect(
                self.start_blender_processing_signal.emit
            )

    # def launch_export_to_blender_thread_worker(
    #     self, session_folder_path: Union[str, Path]
    # ):
    #     logger.info("Launching `Export to Blender` thread worker...")
    #
    #     self._export_to_blender_thread_worker = ExportToBlenderThreadWorker(
    #         session_folder_path
    #     )
    #     self._export_to_blender_thread_worker.finished.connect(
    #         self.blender_file_created_signal.emit
    #     )
    #     self._export_to_blender_thread_worker.start()
    def launch_3d_visualization_thread(self):
        pass
