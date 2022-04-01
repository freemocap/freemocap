import logging
import time
import traceback
from pathlib import Path

import cv2
import numpy as np

from src.cameras.multicam_manager.cv_camera_manager import OpenCVCameraManager
from src.cameras.persistence.video_writer.save_options_dataclass import SaveOptions
from src.config.data_paths import freemocap_data_path
from src.core_processor.camera_calibration.camera_calibrator import CameraCalibrator
from src.core_processor.fps.fps_counter import FPSCamCounter
from src.core_processor.mediapipe_skeleton_detection.mediapipe_skeleton_detection import MediaPipeSkeletonDetection
from src.core_processor.show_cam_window import show_cam_window
from src.qt_visualizer_and_gui.qt_visualizer_and_gui import QTVisualizerAndGui

logger = logging.getLogger(__name__)


def get_canonical_time_str():
    return time.strftime("%m-%d-%Y-%H_%M_%S")


class SessionPipelineOrchestrator:
    def __init__(self):
        self._session_start_time = time.time_ns()
        self._session_id = 'session_' + time.strftime("%m-%d-%Y-%H_%M_%S")
        self._visualizer_gui = QTVisualizerAndGui()
        self._open_cv_camera_manager = OpenCVCameraManager(session_id=self._session_id)
        self._camera_calibrator = CameraCalibrator()
        self._mediapipe_skeleton_detector = MediaPipeSkeletonDetection(model_complexity=0)

    @property
    def session_folder_path(self):
        return freemocap_data_path / self._session_id

    async def process_by_cam_id(self, webcam_id: str, cb):
        with self._open_cv_camera_manager.start_capture_session_single_cam(
                webcam_id=webcam_id,
        ) as session_obj:
            fps_manager = FPSCamCounter(self._open_cv_camera_manager.available_webcam_ids)
            fps_manager.start_all()
            cv_cam = session_obj.cv_camera
            writer = session_obj.video_recorder
            try:
                while True:
                    if not cv_cam.is_capturing_frames:
                        logger.debug(f'Camera {webcam_id} is not capturing frames')
                        continue

                    if self.calibrate_cameras:
                        charuco_frame_payload = self._camera_calibrator.calibrate(cv_cam)

                    if cb and charuco_frame_payload.annotated_image is not None:
                        writer.record(charuco_frame_payload.raw_frame_payload)
                        await cb(charuco_frame_payload.annotated_image)
            except Exception as e:
                logger.error("Printing traceback")
                traceback.print_exc()
                raise e
            finally:
                writer = session_obj.video_recorder
                options = SaveOptions(
                    writer_dir=Path().joinpath(
                        cv_cam.session_writer_base_path,
                        "charuco_board_detection",
                        f"webcam_{cv_cam.webcam_id_as_str}",
                    ),
                    fps=fps_manager.current_fps_for(cv_cam.webcam_id_as_str),
                    frame_width=cv_cam.image_width(),
                    frame_height=cv_cam.image_height(),
                )
                writer.save_to_disk(options)

    def run(
            self,
            show_camera_views_in_windows=True,
            show_visualizer_gui=True,
            calibrate_cameras=True,
            detect_skeleton=True,
            save_video=True,
    ):
        """
        Opens Cameras using OpenCV and begins image processing for charuco board
        If return images is true, the images are returned to the caller
        """

        with self._open_cv_camera_manager.start_capture_session_all_cams() as connected_cameras_dict:

            try:
                fps_manager = FPSCamCounter(self._open_cv_camera_manager.available_webcam_ids)
                fps_manager.start_all()

                self._visualizer_gui.setup_and_launch(self._open_cv_camera_manager.available_webcam_ids)

                should_continue = True
                while should_continue:

                    if not self._open_cv_camera_manager.new_synchronized_frame_available():
                        continue
                    this_frame_timestamps_dict = {}
                    incoming_synchronized_frame_dict = self._open_cv_camera_manager.latest_synchronized_frame()

                    for this_webcam_id, this_open_cv_camera in connected_cameras_dict.items():

                        this_cam_latest_sync_frame = incoming_synchronized_frame_dict[this_webcam_id]

                        if this_cam_latest_sync_frame is None:
                            image_to_display = this_open_cv_camera.latest_frame #if this camera has no new frame, write the previous one instead
                            this_frame_timestamps_dict[this_webcam_id] = np.nan # a `nan` timestamp denotes a dropped frame
                        else:
                            this_frame_timestamps_dict[
                                this_webcam_id] = (this_cam_latest_sync_frame.timestamp - self._session_start_time)/1e6 #milliseconds, I think
                            image_to_display = this_cam_latest_sync_frame.image

                        if save_video:
                            # print('sending frame to be written')
                            this_open_cv_camera.video_recorder.record(this_cam_latest_sync_frame)

                        if calibrate_cameras:
                            undistorted_annotated_image = self._camera_calibrator.calibrate(this_open_cv_camera)
                            image_to_display = undistorted_annotated_image

                        if detect_skeleton:
                            image_to_display = self._mediapipe_skeleton_detector.detect_skeleton_in_image(image_to_display)

                        fps_manager.increment_frame_processed_for(this_webcam_id)
                        if show_camera_views_in_windows:
                            should_continue = show_cam_window(
                                this_webcam_id, image_to_display, fps_manager
                            )

                        if show_visualizer_gui:
                            self._visualizer_gui.update_camera_view_image(this_webcam_id, image_to_display)
                            if len(this_frame_timestamps_dict.keys()) == self._open_cv_camera_manager.number_of_cameras:
                                self._visualizer_gui.update_timestamp_plots(this_frame_timestamps_dict)

            except:
                logger.error("Printing traceback")
                traceback.print_exc()
            finally:
                for this_open_cv_camera in connected_cameras_dict.values():
                    if save_video:
                        this_open_cv_camera.video_recorder.save_to_disk(self.session_folder_path / 'synchronized_videos')
                    logger.info(f"Destroy window {this_open_cv_camera.webcam_id_as_str}")
                    cv2.destroyWindow(this_open_cv_camera.webcam_id_as_str)
                    cv2.waitKey(1)

                self._visualizer_gui.close()


if __name__ == "__main__":
    print('start main')

    this_session = SessionPipelineOrchestrator()
    this_session.run(calibrate_cameras=True)
