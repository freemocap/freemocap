import logging
import time
from typing import Dict

import traceback

import cv2

from src.cameras.multicam_manager.cv_camera_manager import OpenCVCameraManager
from src.config.webcam_config import WebcamConfig
import asyncio

from src.core_processor.show_cam_window import show_cam_window
from src.pipelines.calibration_pipeline.charuco_board_detection.charuco_board_detector import CharucoBoardDetector

logger = logging.getLogger(__name__)


def launch_camera_frame_loop(
        session_id: str,
        webcam_configs_dict: Dict[str, WebcamConfig] = None,
        opencv_camera_manager: OpenCVCameraManager = None,
        show_camera_views_in_windows: bool = False,
        calibration_videos_bool: bool = False,
        detect_charuco_in_image: bool = True,
        camera_view_update_function=None,
        update_gui_function = None,
        exit_event_bool:bool = False,
):

    any_frames_recorded = False

    if detect_charuco_in_image:
        charuco_board_detector = CharucoBoardDetector()

    if opencv_camera_manager is None:
        opencv_camera_manager = OpenCVCameraManager(session_id=session_id,
                                                     expected_framerate=None)

    with opencv_camera_manager.start_capture_session_all_cams(webcam_configs_dict=webcam_configs_dict,
                                                              camera_view_update_function=camera_view_update_function,
                                                              calibration_videos=calibration_videos_bool, ) as connected_cameras_dict:
        try:
            should_continue = True
            while should_continue:

                if update_gui_function is None:
                    update_gui_function()

                for this_webcam_id, this_opencv_camera in connected_cameras_dict.items():
                    this_frame_payload = this_opencv_camera.latest_frame

                    image_to_display = this_frame_payload.image

                    if detect_charuco_in_image:
                        this_charuco_frame_payload = charuco_board_detector.detect_charuco_board(
                            this_frame_payload)
                        image_to_display = this_charuco_frame_payload.annotated_image

                    if show_camera_views_in_windows:
                        should_continue = show_cam_window(
                            this_webcam_id,
                            image_to_display,
                            opencv_camera_manager.timestamp_manager
                        )

                    # exit loop when user presses ESC key
                    exit_key = cv2.waitKey(1)
                    if exit_key == 27:
                        logger.info("ESC has been pressed.")
                        should_continue = False

                    if exit_event_bool is not None:
                        if exit_event_bool:
                            should_continue = False
        except:
            logger.error("Printing traceback")
            traceback.print_exc()
        finally:

            for this_open_cv_camera in connected_cameras_dict.values():
                if any_frames_recorded:
                    this_open_cv_camera.video_recorder.save_list_of_frames_to_video_file(
                        this_open_cv_camera.video_recorder.frame_list)
                this_open_cv_camera.video_recorder.close()
                this_open_cv_camera.close()
