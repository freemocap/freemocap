import logging
import time
import traceback
from pathlib import Path

import cv2

from src.cameras.multicam_manager.cv_camera_manager import OpenCVCameraManager
from src.cameras.persistence.video_writer.save_options import SaveOptions
from src.core_processor.camera_calibration.camera_calibrator import CameraCalibrator
from src.core_processor.fps.fps_counter import FPSCamCounter
from src.core_processor.show_cam_window import show_cam_window

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self,
                 opencv_camera_manager: OpenCVCameraManager = OpenCVCameraManager(),
                 calibrate_cameras: bool = True
                 ):
        self._open_cv_camera_manager = opencv_camera_manager
        self.calibrate_cameras = calibrate_cameras
        if self.calibrate_cameras:
            self.camera_calibrator = CameraCalibrator()
        self._start_time = time.time()

    async def process_by_cam_id(self, webcam_id: str, cb):
        with self._open_cv_camera_manager.start_capture_session_single_cam(
                webcam_id=webcam_id,
        ) as session_obj:
            fps_manager = FPSCamCounter(self._open_cv_camera_manager.available_webcam_ids)
            fps_manager.start_all()
            cv_cam = session_obj.cv_cam
            writer = session_obj.writer
            try:
                while True:
                    if not cv_cam.is_capturing_frames:
                        return
                    charuco_frame_payload = self._board_detection_object.detect_charuco_board_in_camera_stream(cv_cam)
                    if cb and charuco_frame_payload.annotated_image is not None:
                        writer.write(charuco_frame_payload.raw_frame_payload)
                        await cb(charuco_frame_payload.annotated_image)
            except Exception as e:
                logger.error("Printing traceback")
                traceback.print_exc()
                raise e
            finally:
                writer = session_obj.writer
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
                writer.save(options)

    def run(
            self,
            show_camera_views_in_windows=True,
            save_video=True,
    ):
        """
        Opens Cameras using OpenCV and begins image processing for charuco board
        If return images is true, the images are returned to the caller
        """
        # if its already capturing frames, this is a no-op

        with self._open_cv_camera_manager.start_capture_session_all_cams() as session_obj:
            fps_manager = FPSCamCounter(self._open_cv_camera_manager.available_webcam_ids)
            fps_manager.start_all()
            try:
                should_continue = True
                while should_continue:
                    for response in session_obj:
                        this_open_cv_camera = response.cv_cam
                        this_video_writer_object = response.writer

                        this_webcam_id = this_open_cv_camera.webcam_id_as_str
                        this_cam_latest_frame = this_open_cv_camera.latest_frame

                        if this_cam_latest_frame.image is None:
                            continue

                        image_to_display = this_cam_latest_frame.image

                        if save_video:
                            this_video_writer_object.write(this_cam_latest_frame)

                        if self.calibrate_cameras:
                            undistorted_annotated_image = self.camera_calibrator.calibrate(this_open_cv_camera)
                            image_to_display = undistorted_annotated_image

                        fps_manager.increment_frame_processed_for(this_webcam_id)
                        if show_camera_views_in_windows:
                            should_continue = show_cam_window(
                                this_webcam_id, image_to_display, fps_manager
                            )
            except:
                logger.error("Printing traceback")
                traceback.print_exc()
            finally:
                for response in session_obj:
                    this_open_cv_camera = response.cv_cam
                    this_video_writer_object = response.writer
                    options = SaveOptions(
                        writer_dir=Path().joinpath(
                            this_open_cv_camera.session_writer_base_path,
                            "charuco_board_detection",
                            f"webcam_{this_open_cv_camera.webcam_id_as_str}",
                        ),
                        fps=fps_manager.current_fps_for(this_open_cv_camera.webcam_id_as_str),
                        frame_width=this_open_cv_camera.image_width,
                        frame_height=this_open_cv_camera.image_height,
                    )
                    this_video_writer_object.save(options)
                    logger.info(f"Destroy window {this_open_cv_camera.webcam_id_as_str}")
                    cv2.destroyWindow(this_open_cv_camera.webcam_id_as_str)
                    cv2.waitKey(1)


    def stop(self):
        if self.calibrate_cameras:
            self.camera_calibrator.lens_distortion_calibrator.calibration_diagnostics_visualizer.close()



if __name__ == "__main__":
    print('start main')

    this_session = SessionManager(calibrate_cameras=True)
    this_session.run()
    this_session.stop()
