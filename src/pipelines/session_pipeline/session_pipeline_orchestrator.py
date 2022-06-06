import time
import logging
import traceback
from pathlib import Path
from typing import Dict, Union

import cv2
import numpy as np

from src.cameras.multicam_manager.cv_camera_manager import OpenCVCameraManager
from src.cameras.persistence.video_writer.save_options_dataclass import SaveOptions
from src.config.data_paths import freemocap_data_path
from src.config.home_dir import create_session_id
from src.core_processor.camera_calibration.camera_calibrator import CameraCalibrator
from src.core_processor.fps.timestamp_manager import TimestampManager
from src.core_processor.mediapipe_skeleton_detection.mediapipe_skeleton_detection import MediaPipeSkeletonDetection
from src.core_processor.show_cam_window import show_cam_window
from src.core_processor.utils.image_fps_writer import write_fps_to_image
from src.pipelines.calibration_pipeline.calibration_pipeline_orchestrator import CalibrationPipelineOrchestrator

from src.pipelines.session_pipeline.data_classes.data_3d_single_frame_payload import Data3dSingleFramePayload
from src.qt_visualizer_and_gui.qt_visualizer_and_gui import QTVisualizerAndGui

logger = logging.getLogger(__name__)


def get_canonical_time_str():
    return time.strftime("%m-%d-%Y-%H_%M_%S")


class SessionPipelineOrchestrator:

    def __init__(self, session_id: str = None):

        if session_id is not None:
            self._session_id = session_id
        else:
            self._session_id = create_session_id()

        self._session_start_time_unix_ns = time.time_ns()
        self._visualizer_gui = QTVisualizerAndGui()
        self._open_cv_camera_manager = OpenCVCameraManager(session_id=self._session_id)
        self._camera_calibrator = CameraCalibrator()
        self._charuco_board_detector = self._camera_calibrator.charuco_board_detector
        self._mediapipe_skeleton_detector = MediaPipeSkeletonDetection(model_complexity=2)

        self._multi_frame_timestamp_intervals_sec = []

    @property
    def session_id(self):
        return self._session_id

    @property
    def session_folder_path(self):
        return freemocap_data_path / self._session_id

    async def process_by_cam_id(self, webcam_id: str, cb):
        with self._open_cv_camera_manager.start_capture_session_single_cam(
                webcam_id=webcam_id,
        ) as session_obj:
            fps_manager = TimestampManager(self._open_cv_camera_manager.available_webcam_ids)
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
                        writer.append_frame_to_list(charuco_frame_payload.raw_frame_payload)
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
                    fps=fps_manager.median_frames_per_second_for_webcam(cv_cam.webcam_id_as_str),
                    frame_width=cv_cam.image_width(),
                    frame_height=cv_cam.image_height(),
                )
                writer.save_frame_list_to_disk(options)

    def calibrate_camera_capture_volume(self, use_most_recent_calibration: bool = False,
                                        load_calibration_from_session_id: str = None):

        if use_most_recent_calibration:
            self._anipose_camera_calibration_object = CalibrationPipelineOrchestrator().load_most_recent_calibration()
            return
        elif load_calibration_from_session_id is not None:
            calibration_orchestrator = CalibrationPipelineOrchestrator(load_calibration_from_session_id)
        else:  # create new calibration
            calibration_orchestrator = CalibrationPipelineOrchestrator(self.session_id)
            calibration_orchestrator.record_videos(show_visualizer_gui=False,
                                                   save_video_in_frame_loop=False,
                                                   show_camera_views_in_windows=True,
                                                   )

        self._anipose_camera_calibration_object = calibration_orchestrator.run_anipose_camera_calibration(
            charuco_square_size=39)

    def run_big_old_bongo_frame_loop(
            self,
            show_camera_views_in_windows=True,
            show_visualizer_gui=True,
            detect_mediapipe=True,
            detect_charuco=True,
            reconstruct_3d=True,
            save_video=True,
    ):
        self._multi_frames_processed = 0

        with self._open_cv_camera_manager.start_capture_session_all_cams() as connected_cameras_dict:
            self._number_of_cameras = len(connected_cameras_dict)
            if detect_charuco:
                incoming_charuco_frame_data_per_camera_dict = {}
                for this_webcam_id in connected_cameras_dict.keys():
                    incoming_charuco_frame_data_per_camera_dict[this_webcam_id] = []

            try:
                if show_visualizer_gui:
                    self._visualizer_gui.setup_and_launch(self._open_cv_camera_manager.available_webcam_ids)

                timestamp_manager = TimestampManager(self._open_cv_camera_manager.available_webcam_ids,
                                                     self._session_start_time_unix_ns)

                should_continue = True
                while should_continue:  # BIG FRAME LOOP STARTS HERE

                    timestamp_manager.increment_main_loop_timestamp_logger(time.perf_counter_ns())

                    # reconstruct 3d data, if there's enough new data to so
                    if reconstruct_3d:
                        if detect_charuco:
                            charuco_frame_payload = self._reconstruct_3d_charuco(incoming_charuco_frame_data_per_camera_dict)
                            if show_visualizer_gui:
                                self._visualizer_gui.update_3d_view_port(charuco_frame_payload, type='charuco')
                    for this_webcam_id, this_open_cv_camera in connected_cameras_dict.items():

                        if not this_open_cv_camera.new_frame_ready:
                            continue

                        this_cam_latest_frame = this_open_cv_camera.latest_frame

                        if this_cam_latest_frame is None:
                            continue

                        image_to_display = this_cam_latest_frame.image.copy()
                        this_cam_this_frame_timestamp_ns = this_cam_latest_frame.timestamp

                        timestamp_manager.increment_frame_processed_for_webcam(this_webcam_id,
                                                                               this_cam_this_frame_timestamp_ns)

                        if save_video:
                            this_open_cv_camera.video_recorder.append_frame_to_list(this_cam_latest_frame)

                        if detect_mediapipe:
                            image_to_display = self._mediapipe_skeleton_detector.detect_skeleton_in_image(
                                image_to_display)

                        if detect_charuco:
                            charuco_frame_payload = self._charuco_board_detector.detect_charuco_board(
                                this_cam_latest_frame)
                            incoming_charuco_frame_data_per_camera_dict[this_webcam_id].append(
                                charuco_frame_payload)

                            image_to_display = charuco_frame_payload.annotated_image

                        if show_camera_views_in_windows:
                            should_continue = show_cam_window(
                                this_webcam_id, image_to_display, timestamp_manager
                            )

                        if show_visualizer_gui:
                            write_fps_to_image(
                                image_to_display,
                                timestamp_manager.median_frames_per_second_for_webcam(this_webcam_id),
                            )
                            self._visualizer_gui.update_camera_view_image(this_webcam_id, image_to_display)
                            self._visualizer_gui.update_timestamp_plots(timestamp_manager)

                        # exit loop when user presses ESC key
                        exit_key = cv2.waitKey(1)
                        if exit_key == 27:
                            logger.info("ESC has been pressed.")
                            should_continue = False

            except:
                logger.error("Printing traceback")
                traceback.print_exc()
            finally:
                for this_open_cv_camera in connected_cameras_dict.values():
                    if save_video:
                        this_open_cv_camera.video_recorder.save_frame_list_to_disk(
                            self.session_folder_path / 'synchronized_videos')
                    logger.info(f"Destroy window {this_open_cv_camera.webcam_id_as_str}")
                    cv2.destroyWindow(this_open_cv_camera.webcam_id_as_str)
                    cv2.waitKey(1)

                if show_visualizer_gui:
                    self._visualizer_gui.close()

    def _reconstruct_3d_charuco(self, incoming_charuco_frame_data_per_camera_dict) -> \
            Union[None, Data3dSingleFramePayload]:

        next_multi_frame_number = self._multi_frames_processed

        new_multi_frame_ready = []
        for this_cam_data_list in incoming_charuco_frame_data_per_camera_dict.values():
            new_multi_frame_ready.append(len(this_cam_data_list) > next_multi_frame_number)

        if not all(new_multi_frame_ready):
            return

        # new multiframe!
        self._multi_frames_processed += 1

        this_multi_frame_charuco_data = []
        this_multi_frame_timestamps = []
        each_cam_number_of_frames = []
        any_charuco_data = []
        for this_webcam_id in incoming_charuco_frame_data_per_camera_dict.keys():
            this_cam_data_list = incoming_charuco_frame_data_per_camera_dict[this_webcam_id]
            each_cam_number_of_frames.append(len(this_cam_data_list))
            this_cam_this_frame = this_cam_data_list[next_multi_frame_number]
            this_multi_frame_timestamps.append(this_cam_this_frame.raw_frame_payload.timestamp)
            this_multi_frame_charuco_data.append(this_cam_this_frame)
            any_charuco_data.append(this_cam_this_frame.charuco_view_data.some_charuco_corners_found)

        timestamp_min = np.min(this_multi_frame_timestamps)
        timestamp_max = np.max(this_multi_frame_timestamps)
        this_multiframe_timestamp_interval_sec = (timestamp_max - timestamp_min) / 1e9
        self._multi_frame_timestamp_intervals_sec.append(this_multiframe_timestamp_interval_sec)

        print(f"TODO:sync with timestamps, not frame index - multi_frame#: {self._multi_frames_processed - 1},"
              f" each_cam_#_of_frames: {each_cam_number_of_frames}, "
              f" intra_multi_frame_timestamp_range: {this_multiframe_timestamp_interval_sec:.3f}", )

        min_cameras_to_reconstruct = 2
        if sum(any_charuco_data) > min_cameras_to_reconstruct:  # if at least 2 cameras have any data, then we can try to make some 3d dottos
            charuco2d_data_per_cam_dict = self.format_charuco2d_data(this_multi_frame_charuco_data)
            charuco_3d_data_payload = self._triangulate_2d_data(charuco2d_data_per_cam_dict,
                                                                self._charuco_board_detector.number_of_charuco_corners)
            return charuco_3d_data_payload

    def format_charuco2d_data(self, this_multi_frame_charuco_data) -> Dict:

        number_of_tracked_points = this_multi_frame_charuco_data[
            0].charuco_view_data.charuco_board_object.number_of_charuco_corners

        charuco2d_data_per_cam_dict = {}
        base_charuco_data_npy_with_nans_for_missing_data_xy = np.zeros((number_of_tracked_points, 2))
        base_charuco_data_npy_with_nans_for_missing_data_xy[:] = np.nan
        for this_cam_data in this_multi_frame_charuco_data:
            this_frame_charuco_data_xy = base_charuco_data_npy_with_nans_for_missing_data_xy.copy()
            charuco_ids_in_this_frame_idx = this_cam_data.charuco_view_data.charuco_ids
            charuco_corners_in_this_frame_xy = this_cam_data.charuco_view_data.charuco_corners
            this_frame_charuco_data_xy[charuco_ids_in_this_frame_idx, :] = charuco_corners_in_this_frame_xy

            this_webcam_id = this_cam_data.raw_frame_payload.webcam_id
            charuco2d_data_per_cam_dict[this_webcam_id] = this_frame_charuco_data_xy

        return charuco2d_data_per_cam_dict

    def _triangulate_2d_data(self, data2d_per_cam_dict: Dict,
                             number_of_tracked_points: int) -> Data3dSingleFramePayload:

        each_cam2d_data_list = [this_cam_charuco2d_frame_xy for this_cam_charuco2d_frame_xy in
                                data2d_per_cam_dict.values()]
        data2d_trackedPointNum_xyz_camNum = np.dstack(
            each_cam2d_data_list)  # stack lists (in depth) to make one numpy array with dimensions [number_of_tracked_points, XYZ, number_of_cameras]
        data2d_camNum_trackedPointNum_xyz = data2d_trackedPointNum_xyz_camNum.reshape(self._number_of_cameras,
                                                                                      number_of_tracked_points,
                                                                                      2)  # reshape to fit into anipose (new dimensions [number_of_cameras, number_of_tracked_points, XYZ]

        # THIS IS WHERE THE MAGIC HAPPENS - 2d data from calibrated, synchronized cameras has now become a 3d estimate. Hurray! :`D
        data3d_trackedPointNum_xyz = self._anipose_camera_calibration_object.triangulate(
            data2d_camNum_trackedPointNum_xyz,
            progress=True)

        # Reprojection error is a measure of the quality of the reconstruction. It is the distance (error) between the original 2d point and a reprojection of the 3d point back onto the image plane.
        # TODO - use this for filtering data (i.e. if one view has very high reprojection error, re-do the triangulation without that camera's view data)
        # TODO - we are currently using each tracking method's `confidence` values (or whatever they choose to call it) for thresholding, but it's problematic because of the neural_networks' propensity to apply high confidence to bonkers estimates, which leads to SPOOKY GHOST SKELETONS! :O
        data3d_trackedPointNum_reprojectionError = self._anipose_camera_calibration_object.reprojection_error(
            data3d_trackedPointNum_xyz,
            data2d_camNum_trackedPointNum_xyz,
            mean=True)

        return Data3dSingleFramePayload(data3d_trackedPointNum_xyz=data3d_trackedPointNum_xyz,
                                        data3d_trackedPointNum_reprojectionError=data3d_trackedPointNum_reprojectionError, )


if __name__ == "__main__":
    print('running `session_pipeline_orchestrator` as `__main__')

    this_session_orchestrator = SessionPipelineOrchestrator()
    this_session_orchestrator.calibrate_camera_capture_volume(use_most_recent_calibration=True)
    # this_session_orchestrator.calibrate_camera_capture_volume()
    this_session_orchestrator.run_big_old_bongo_frame_loop(show_camera_views_in_windows=False,
                                                           save_video=False,
                                                           show_visualizer_gui=True,
                                                           detect_mediapipe=False,
                                                           detect_charuco=True,
                                                           reconstruct_3d=True,
                                                           )
