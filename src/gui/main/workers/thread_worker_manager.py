import logging
from pathlib import Path
from typing import Callable, Dict, List, Union

import numpy as np
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget

from old_src.cameras.detection.models import FoundCamerasResponse
from old_src.cameras.persistence.video_writer.video_recorder import VideoRecorder
from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import (
    CharucoBoardDefinition,
)
from old_src.gui.main.workers.anipose_calibration_thread_worker import (
    AniposeCalibrationThreadWorker,
)
from old_src.gui.main.workers.cam_detection_thread_worker import (
    CameraDetectionThreadWorker,
)
from old_src.gui.main.workers.convert_npy_to_csv_thread_worker import (
    ConvertNpyToCsvThreadWorker,
)
from old_src.gui.main.workers.mediapipe_2d_detection_thread_worker import (
    Mediapipe2dDetectionThreadWorker,
)
from old_src.gui.main.workers.post_process_3d_data_thread_worker import (
    PostProcess3dDataThreadWorker,
)
from old_src.gui.main.workers.save_to_video_thread_worker import SaveToVideoThreadWorker
from old_src.gui.main.workers.session_playback_thread_worker import (
    SessionPlaybackThreadWorker,
)
from old_src.gui.main.workers.triangulate_3d_data_thread_worker import (
    Triangulate3dDataThreadWorker,
)

logger = logging.getLogger(__name__)


class ThreadWorkerManager(QWidget):
    """This guy's job is to hold on to the parts of threads that need to be kept alive while they are running"""

    camera_detection_finished = pyqtSignal(FoundCamerasResponse)
    videos_saved_signal = pyqtSignal(bool)
    start_3d_processing_signal = pyqtSignal()
    start_post_processing_signal = pyqtSignal()
    start_convert_npy_to_to_csv_signal = pyqtSignal()
    start_session_data_visualization_signal = pyqtSignal()
    start_blender_processing_signal = pyqtSignal()
    blender_file_created_signal = pyqtSignal(str)

    def __init__(self, session_progress_dictionary: dict):
        super().__init__()
        self._session_progress_dictionary = session_progress_dictionary

    @property
    def session_progress_dictionary(self) -> dict:
        return self._session_progress_dictionary

    def launch_detect_cameras_worker(self):
        logger.info("Launching `Camera Detection` thread worker")

        self._session_progress_dictionary["camera_detection"] = "launched"

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

        if calibration_videos:
            self._session_progress_dictionary["save_calibrate_videos"] = "launched"
        else:
            self._session_progress_dictionary["save_mocap_videos"] = "launched"

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
        charuco_board_definition: CharucoBoardDefinition,
        calibration_videos_folder_path: Union[str, Path],
        charuco_square_size_mm: float,
        session_id: str,
        jupyter_console_print_function_callable: Callable,
    ):
        logger.info("Launching `Anipose (Charuco Board) Calibration` thread worker")
        self._session_progress_dictionary["anipose_calibration"] = "launched"
        self._anipose_calibration_worker = AniposeCalibrationThreadWorker(
            charuco_board_definition=charuco_board_definition,
            calibration_videos_folder_path=calibration_videos_folder_path,
            charuco_square_size=charuco_square_size_mm,
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
        self._session_progress_dictionary["medipipe"] = "launched"
        self._mediapipe_2d_detection_thread_worker = Mediapipe2dDetectionThreadWorker(
            path_to_folder_of_videos_to_process=synchronized_videos_folder_path,
            output_data_folder_path=output_data_folder_path,
        )

        if auto_process_next_stage:
            logger.info("Emitting `start_3d_processing_signal`")
            self._mediapipe_2d_detection_thread_worker.finished.connect(
                self.start_3d_processing_signal.emit
            )
        self._mediapipe_2d_detection_thread_worker.start()

    def launch_triangulate_3d_data_thread_worker(
        self,
        anipose_calibration_object,
        mediapipe_2d_data: np.ndarray,
        output_data_folder_path: Union[str, Path],
        mediapipe_confidence_cutoff_threshold: float,
        auto_process_next_stage: bool = False,
        use_triangulate_ransac: bool = False,
    ):
        logger.info("Launching `Triangulate 3d Data` thread worker...")
        self._session_progress_dictionary["triangulate"] = "launched"
        self._triangulate_3d_data_thread_worker = Triangulate3dDataThreadWorker(
            anipose_calibration_object=anipose_calibration_object,
            mediapipe_2d_data=mediapipe_2d_data,
            output_data_folder_path=output_data_folder_path,
            mediapipe_confidence_cutoff_threshold=mediapipe_confidence_cutoff_threshold,
            use_triangulate_ransac=use_triangulate_ransac,
        )

        self._triangulate_3d_data_thread_worker.start()

        if auto_process_next_stage:
            logger.info("Emitting `start_post_processing_signal`")
            self._triangulate_3d_data_thread_worker.finished.connect(
                self.start_post_processing_signal.emit
            )

    def launch_post_process_3d_data_thread_worker(
        self,
        skel3d_frame_marker_xyz: np.ndarray,
        skeleton_reprojection_error_fr_mar: np.ndarray,
        data_save_path: Union[str, Path],
        sampling_rate: int,
        cut_off: float,
        order: int,
        reference_frame_number: int = None,
        auto_process_next_stage: bool = False,
    ):
        logger.info("Launching `Post Process 3d Data` thread worker...")
        self._session_progress_dictionary["post_process"] = "launched"
        self._post_process_3d_data_thread_worker = PostProcess3dDataThreadWorker(
            skel3d_frame_marker_xyz=skel3d_frame_marker_xyz,
            skeleton_reprojection_error_fr_mar=skeleton_reprojection_error_fr_mar,
            data_save_path=data_save_path,
            sampling_rate=sampling_rate,
            cut_off=cut_off,
            order=order,
            reference_frame_number=reference_frame_number,
        )
        self._post_process_3d_data_thread_worker.start()

        if auto_process_next_stage:
            logger.info("Emitting `convert_to_csv_signal`")
            self._post_process_3d_data_thread_worker.finished.connect(
                self.start_convert_npy_to_to_csv_signal.emit
            )

    def launch_convert_npy_to_csv_thread_worker(
        self,
        skel3d_frame_marker_xyz: np.ndarray,
        output_data_folder_path: Union[str, Path],
        auto_process_next_stage: bool = False,
    ):
        logger.info("Launching `Convert Npy to Csv` thread worker...")
        self._session_progress_dictionary["convert_to_csv"] = "launched"
        self._convert_npy_to_csv_thread_worker = ConvertNpyToCsvThreadWorker(
            skel3d_frame_marker_xyz=skel3d_frame_marker_xyz,
            output_data_folder_path=output_data_folder_path,
        )
        self._convert_npy_to_csv_thread_worker.start()

        if auto_process_next_stage:
            logger.info("Emitting `start_session_data_visualization_signal`")
            self._convert_npy_to_csv_thread_worker.finished.connect(
                self.start_session_data_visualization_signal.emit
            )
            logger.info("Emitting `start_blender_processing_signal`")
            self._convert_npy_to_csv_thread_worker.finished.connect(
                self.start_blender_processing_signal.emit
            )

    def launch_session_playback_thread(
        self,
        frames_per_second: Union[int, float],
        list_of_video_paths: List[Union[str, Path]],
        dictionary_of_video_image_update_callbacks: Dict[str, Callable],
        skeleton_3d_npy: np.ndarray,
        update_3d_skeleton_callback: Callable,
    ):
        logger.info(
            f"Launching `session_playback_thread_worker` with frames_per_second set to {frames_per_second} "
        )
        self._session_progress_dictionary["launch_session_playback"] = "launched"
        self._session_playback_viewer_thread_worker = SessionPlaybackThreadWorker(
            frames_per_second=frames_per_second,
            list_of_video_paths=list_of_video_paths,
            dictionary_of_video_image_update_callbacks=dictionary_of_video_image_update_callbacks,
            skeleton_3d_npy=skeleton_3d_npy,
            update_3d_skeleton_callback=update_3d_skeleton_callback,
        )
        self._session_playback_viewer_thread_worker.start()
