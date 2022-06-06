import time
import logging
import traceback
from pathlib import Path
from typing import Union

import cv2

from src.cameras.multicam_manager.cv_camera_manager import OpenCVCameraManager
from src.config.home_dir import create_session_id, get_session_path, get_freemocap_data_folder_path
from src.core_processor.fps.timestamp_manager import TimestampManager
from src.core_processor.show_cam_window import show_cam_window
from src.core_processor.utils.image_fps_writer import write_fps_to_image
from src.pipelines.calibration_pipeline.anipose_camera_calibration import freemocap_anipose
from src.pipelines.calibration_pipeline.anipose_camera_calibration.anipose_camera_calibration import \
    AniposeCameraCalibrator
from src.pipelines.calibration_pipeline.charuco_board_detection.charuco_board_detector import CharucoBoardDetector
from src.qt_visualizer_and_gui.qt_visualizer_and_gui import QTVisualizerAndGui

logger = logging.getLogger(__name__)


class CalibrationPipelineOrchestrator:

    def __init__(self, session_id:str=None):

        if session_id is not None:
            self._session_id = session_id
            self._calibration_start_time_unix_ns = time.time_ns()
            self._charuco_board_detector = CharucoBoardDetector()
            self._visualizer_gui = QTVisualizerAndGui(source='calibration')
            self._open_cv_camera_manager = OpenCVCameraManager(session_id=self._session_id)

    @property
    def session_id(self):
        return self._session_id

    @property
    def session_folder_path(self):
        return get_session_path(self._session_id)

    def record_videos(
            self,
            show_visualizer_gui=True,
            show_camera_views_in_windows=True,
            save_video_in_frame_loop=False,

    ):
        """open all cameras and start recording, detect charuco boards until the user closes the windows, then send recorded videos to `aniposelib` for processing
        produces `[session_id]_calibration.toml` file that can be used to estiamte 3d trajectorires from synchronized images"""
        with self._open_cv_camera_manager.start_capture_session_all_cams() as connected_cameras_dict:
            try:
                if show_visualizer_gui:
                    self._visualizer_gui.setup_and_launch(self._open_cv_camera_manager.available_webcam_ids)

                timestamp_manager = TimestampManager(self._open_cv_camera_manager.available_webcam_ids,
                                                     self._calibration_start_time_unix_ns)

                should_continue = True
                while should_continue:

                    timestamp_manager.increment_main_loop_timestamp_logger(time.perf_counter_ns())

                    for this_webcam_id, this_open_cv_camera in connected_cameras_dict.items():

                        if not this_open_cv_camera.new_frame_ready:
                            continue

                        this_cam_latest_frame = this_open_cv_camera.latest_frame

                        if this_cam_latest_frame is None:
                            continue

                        # log timestamp
                        this_cam_this_frame_timestamp_ns = this_cam_latest_frame.timestamp
                        this_cam_this_frame_number = this_cam_latest_frame.frame_number
                        timestamp_manager.increment_frame_processed_for_webcam(this_webcam_id,
                                                                               this_cam_this_frame_timestamp_ns,
                                                                               this_cam_this_frame_number)

                        # save frame to video file
                        if save_video_in_frame_loop:
                            # save this frame straight to the video file (no risk of memory overflow, but can't handle higher numbers of cameras)
                            this_open_cv_camera.video_recorder.save_frame_to_video_file(this_cam_latest_frame)
                        else:
                            # can handle large numbers of cameras, but will eventually fill up RAM and cause a crash
                            this_open_cv_camera.video_recorder.append_frame_to_list(this_cam_latest_frame)

                        # detect charuco board
                        this_charuco_frame_payload = self._charuco_board_detector.detect_charuco_board(
                            this_cam_latest_frame)

                        if show_camera_views_in_windows:
                            should_continue = show_cam_window(
                                this_webcam_id, this_charuco_frame_payload.annotated_image, timestamp_manager
                            )

                        if show_visualizer_gui:
                            write_fps_to_image(
                                this_charuco_frame_payload.annotated_image,
                                timestamp_manager.median_frames_per_second_for_webcam(this_webcam_id),
                            )
                            self._visualizer_gui.update_camera_view_image(this_webcam_id,
                                                                          this_charuco_frame_payload.annotated_image)

                        # exit loop when user presses ESC key
                        exit_key = cv2.waitKey(1)
                        if exit_key == 27:
                            logger.info("ESC has been pressed.")
                            should_continue = False

            except:
                logger.error("Printing traceback")
                traceback.print_exc()
            finally:
                if show_camera_views_in_windows:
                    # logger.info(f"Destroy window {this_open_cv_camera.webcam_id_as_str}")
                    # cv2.destroyWindow(this_open_cv_camera.webcam_id_as_str)
                    cv2.destroyAllWindows()
                for this_open_cv_camera in connected_cameras_dict.values():
                    if not save_video_in_frame_loop:
                        this_open_cv_camera.video_recorder.save_frame_list_to_disk()
                    this_open_cv_camera.video_recorder.close()

                if show_visualizer_gui:
                    self._visualizer_gui.close()

    def run_anipose_camera_calibration(self,
                                       charuco_square_size: Union[int, float] = 1,
                                       ):
        anipose_camera_calibrator = AniposeCameraCalibrator(self.session_id,
                                                            self._charuco_board_detector.charuco_board_data_class_object,
                                                            charuco_square_size=charuco_square_size)
        return anipose_camera_calibrator.calibrate_camera_capture_volume()

    def load_most_recent_calibration(self):
        last_successful_calibration_path = Path(get_freemocap_data_folder_path(), "last_successful_calibration.toml")
        logger.info(f"loading `most recent calibration from:{str(last_successful_calibration_path)}")
        return freemocap_anipose.CameraGroup.load(str(last_successful_calibration_path))


if __name__ == "__main__":
    print('running `calibration_pipeline` as a `__main__` file')

    record_new = True
    if record_new:
        session_id = create_session_id('calibration')
        session_path = Path(get_session_path(session_id))
        logger.info(f'Creating `calibration only` session folder at: {str(session_path)}')
        session_path.mkdir(parents=True, exist_ok=False)

        calibration_orchestrator = CalibrationPipelineOrchestrator(session_id)
        calibration_orchestrator.record_videos(show_visualizer_gui=False,
                                               save_video_in_frame_loop=False,
                                               show_camera_views_in_windows=True,
                                               )

    else:
        session_id = "session_06-05-2022-10_31_34_calibration"
        calibration_orchestrator = CalibrationPipelineOrchestrator(session_id)

    calibration_orchestrator.run_anipose_camera_calibration(charuco_square_size=39)
