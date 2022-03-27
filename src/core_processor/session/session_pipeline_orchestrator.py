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
from src.qt_visualizer_and_gui.qt_visualizer_and_gui import QTVisualizerAndGui

logger = logging.getLogger(__name__)

def get_canonical_time_str():
    return time.strftime("%m-%d-%Y-%H_%M_%S")

class SessionPipelineOrchestrator:
    def __init__(self):
        self._session_start_time = time.time()
        self._session_id = 'session_'+time.strftime("%m-%d-%Y-%H_%M_%S")
        self._visualizer_gui = QTVisualizerAndGui()
        self._open_cv_camera_manager = OpenCVCameraManager(session_id=self._session_id)
        self._camera_calibrator = CameraCalibrator()


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
                        logger.debug(f'Camera {webcam_id} is not capturing frames')
                        continue

                    if self.calibrate_cameras:
                        charuco_frame_payload = self._camera_calibrator.calibrate(cv_cam)

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
            show_camera_views_in_gui=True,
            calibrate_cameras = True,
            save_video=True,
    ):
        """
        Opens Cameras using OpenCV and begins image processing for charuco board
        If return images is true, the images are returned to the caller
        """

        with self._open_cv_camera_manager.start_capture_session_all_cams() as cam_and_writer_response_list:

            self._visualizer_gui.setup_and_launch(cam_and_writer_response_list)

            fps_manager = FPSCamCounter(self._open_cv_camera_manager.available_webcam_ids)
            fps_manager.start_all()

            try:
                should_continue = True
                while should_continue:
                    for this_response in cam_and_writer_response_list:

                        this_open_cv_camera = this_response.cv_cam
                        this_video_writer_object = this_response.writer

                        this_webcam_id_as_str = this_open_cv_camera.webcam_id_as_str
                        this_cam_latest_frame = this_open_cv_camera.latest_frame

                        if this_cam_latest_frame.image is None:
                            continue

                        image_to_display = this_cam_latest_frame.image

                        if save_video:
                            this_video_writer_object.write(this_cam_latest_frame)

                        if calibrate_cameras:
                            undistorted_annotated_image = self._camera_calibrator.calibrate(this_open_cv_camera)
                            image_to_display = undistorted_annotated_image

                        fps_manager.increment_frame_processed_for(this_webcam_id_as_str)
                        if show_camera_views_in_windows:
                            should_continue = show_cam_window(
                                this_webcam_id_as_str, image_to_display, fps_manager
                            )

                        if show_camera_views_in_gui:
                            self._visualizer_gui.update_camera_view_image(this_webcam_id_as_str, image_to_display)
            except:
                logger.error("Printing traceback")
                traceback.print_exc()
            finally:
                for this_response in cam_and_writer_response_list:
                    this_open_cv_camera = this_response.cv_cam
                    # this_video_writer_object = this_response.writer
                    # options = SaveOptions(
                    #     path_to_save_video=Path().joinpath(
                    #         this_open_cv_camera.session_writer_base_path,
                    #         "charuco_board_detection",
                    #         f"webcam_{this_open_cv_camera.webcam_id_as_str}",
                    #     ),
                    #     fps=fps_manager.current_fps_for(this_open_cv_camera.webcam_id_as_str),
                    #     frame_width=this_open_cv_camera.image_width,
                    #     frame_height=this_open_cv_camera.image_height,
                    # )
                    # this_video_writer_object.save(options)
                    logger.info(f"Destroy window {this_open_cv_camera.webcam_id_as_str}")
                    cv2.destroyWindow(this_open_cv_camera.webcam_id_as_str)
                    cv2.waitKey(1)

                self._visualizer_gui.close()




if __name__ == "__main__":
    print('start main')

    this_session = SessionPipelineOrchestrator()
    this_session.run(calibrate_cameras=False)
