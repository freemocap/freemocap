import logging
import traceback
from typing import Dict

import cv2

from old_src.cameras.multicam_manager.cv_camera_manager import OpenCVCameraManager
from old_src.cameras.webcam_config import WebcamConfig
from old_src.core_processes.capture_volume_calibration.charuco_board_detection.charuco_board_detector import (
    CharucoBoardDetector,
)
from old_src.core_processes.show_cam_window import show_cam_window
from old_src.core_processes.utils.image_fps_writer import write_fps_to_image
from old_src.qt_visualizer_and_gui.qt_visualizer_and_gui import QTVisualizerAndGui

logger = logging.getLogger(__name__)


def launch_camera_frame_loop(
    session_id: str,
    webcam_configs_dict: Dict[str, WebcamConfig] = None,
    show_camera_views_in_windows: bool = True,
    calibration_videos_bool: bool = False,
    detect_charuco_in_image: bool = True,
    record_frames_bool: bool = True,
    show_visualizer_gui: bool = False,
):
    any_frames_recorded = False

    if detect_charuco_in_image:
        charuco_board_detector = CharucoBoardDetector()

        opencv_camera_manager = OpenCVCameraManager(session_id=session_id)

    with opencv_camera_manager.start_capture_session_all_cams(
        webcam_configs_dict=webcam_configs_dict,
        calibration_videos=calibration_videos_bool,
    ) as connected_cameras_dict:

        timestamp_manager = (
            opencv_camera_manager.timestamp_manager
        )  # <-this is defines the start-time of the timestamp loggers for each camera

        try:

            if show_visualizer_gui:
                visualizer_gui = QTVisualizerAndGui()
                visualizer_gui.setup_and_launch(
                    opencv_camera_manager.available_webcam_ids
                )

            should_continue = True
            while should_continue:

                if not opencv_camera_manager.new_multi_frame_ready():
                    continue

                this_multi_frame_payload = opencv_camera_manager.latest_multi_frame
                timestamp_manager.multi_frame_timestamp_logger.log_new_timestamp_seconds_from_unspecified_zero(
                    this_multi_frame_payload.multi_frame_timestamp_seconds
                )

                for (
                    this_webcam_id,
                    this_open_cv_camera,
                ) in connected_cameras_dict.items():

                    this_cam_latest_frame = this_multi_frame_payload.frames_dict[
                        this_webcam_id
                    ]

                    if this_cam_latest_frame is None:
                        continue

                    this_cam_timestamp_logger = (
                        timestamp_manager.timestamp_logger_for_webcam_id(this_webcam_id)
                    )
                    this_cam_timestamp_logger.log_new_timestamp_seconds_from_unspecified_zero(
                        this_cam_latest_frame.timestamp_in_seconds_from_record_start
                    )

                    # save frame to video file
                    if record_frames_bool:
                        any_frames_recorded = True
                        this_open_cv_camera.video_recorder.append_frame_payload_to_list(
                            this_cam_latest_frame
                        )

                    image_to_display = this_cam_latest_frame.image.copy()

                    if detect_charuco_in_image:
                        # detect charuco board
                        this_charuco_frame_payload = charuco_board_detector.detect_charuco_board_in_frame_payload(
                            this_cam_latest_frame
                        )
                        image_to_display = (
                            this_charuco_frame_payload.annotated_image.copy()
                        )

                    image_to_display = write_fps_to_image(
                        image_to_display,
                        timestamp_manager.timestamp_logger_for_webcam_id(
                            this_webcam_id
                        ).median_frames_per_second,
                    )

                    if show_camera_views_in_windows:
                        should_continue = show_cam_window(
                            this_webcam_id, image_to_display
                        )

                    if show_visualizer_gui:
                        visualizer_gui.update_camera_view_image(
                            this_webcam_id, image_to_display
                        )

                    # exit loop when user presses ESC key
                    exit_key = cv2.waitKey(1)
                    if exit_key == 27:
                        logger.info("ESC has been pressed.")
                        should_continue = False

        except:
            logger.error("Printing traceback")
            traceback.print_exc()
        finally:

            if show_visualizer_gui:
                visualizer_gui.close()
            if show_camera_views_in_windows:
                # logger.info(f"Destroy window {this_open_cv_camera.webcam_id_as_str}")
                # cv2.destroyWindow(this_open_cv_camera.webcam_id_as_str)
                cv2.destroyAllWindows()

            for this_open_cv_camera in connected_cameras_dict.values():
                if any_frames_recorded:
                    logger.info(
                        f"Saving {this_open_cv_camera.webcam_id_as_str} video to disk"
                    )
                    this_open_cv_camera.video_recorder.save_list_of_frames_to_video_file(
                        this_open_cv_camera.video_recorder.frame_list
                    )
                this_open_cv_camera.video_recorder.close()

            logger.info("Creating camera timestamp diagnostic plot")
            timestamp_manager.create_diagnostic_plots()
