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
from src.config.home_dir import create_session_id, get_session_folder_path, get_output_data_folder_path
from src.core_processor.camera_calibration.camera_calibrator import CameraCalibrator
from src.core_processor.timestamp_manager.timestamp_manager import TimestampManager
from src.core_processor.mediapipe_skeleton_detector.mediapipe_skeleton_detector import MediaPipeSkeletonDetector
from src.core_processor.show_cam_window import show_cam_window
from src.core_processor.utils.image_fps_writer import write_fps_to_image
from src.debug_plot_makers.simple_plot_3d_points import simple_plot_3d
from src.pipelines.calibration_pipeline.calibration_pipeline_orchestrator import CalibrationPipelineOrchestrator
from src.pipelines.calibration_pipeline.charuco_board_detection.charuco_board_detector import CharucoBoardDetector
from src.pipelines.session_pipeline.data_classes.data3d_full_session_data import Data3dFullSessionPayload

from src.pipelines.session_pipeline.data_classes.data_3d_single_frame_payload import Data3dSingleFramePayload
from src.qt_visualizer_and_gui.qt_visualizer_and_gui import QTVisualizerAndGui

logger = logging.getLogger(__name__)


def get_canonical_time_str():
    return time.strftime("%m-%d-%Y-%H_%M_%S")


class SessionPipelineOrchestrator:

    def __init__(self, session_id: str = None, expected_framerate: Union[int, float] = None):

        if session_id is not None:
            self._session_id = session_id
        else:
            self._session_id = create_session_id()

        self._expected_framerate = expected_framerate

        self._visualizer_gui = QTVisualizerAndGui()
        self._open_cv_camera_manager = OpenCVCameraManager(session_id=self._session_id,
                                                           expected_framerate=self.expected_framerate)
        self._charuco_board_detector = CharucoBoardDetector()
        self._mediapipe_skeleton_detector = MediaPipeSkeletonDetector(self._session_id)

    @property
    def session_id(self):
        return self._session_id

    @property
    def expected_framerate(self):
        return self._expected_framerate

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
                        writer.append_frame_payload_to_list(charuco_frame_payload.raw_frame_payload)
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
                writer.save_frame_payload_list_to_disk(options)

    def calibrate_camera_capture_volume(self, use_most_recent_calibration: bool = False,
                                        load_calibration_from_session_id: str = None,
                                        charuco_square_size: int = 1,
                                        pin_camera_0_to_origin: bool = False):

        if use_most_recent_calibration:
            self._anipose_camera_calibration_object = CalibrationPipelineOrchestrator().load_most_recent_calibration()
            return
        elif load_calibration_from_session_id is not None:
            calibration_orchestrator = CalibrationPipelineOrchestrator(load_calibration_from_session_id)
        else:  # create new calibration
            calibration_orchestrator = CalibrationPipelineOrchestrator(self.session_id,
                                                                       expected_framerate=self.expected_framerate)
            calibration_orchestrator.record_videos(show_visualizer_gui=False,
                                                   save_video_in_frame_loop=False,
                                                   show_camera_views_in_windows=True,
                                                   )

        self._anipose_camera_calibration_object = calibration_orchestrator.run_anipose_camera_calibration(
            charuco_square_size=charuco_square_size,
            pin_camera_0_to_origin=pin_camera_0_to_origin)

    def record_new_session(
            self,
            show_visualizer_gui=True,
            show_camera_views_in_windows=False,
    ):

        with self._open_cv_camera_manager.start_capture_session_all_cams() as connected_cameras_dict:

            self._number_of_cameras = len(connected_cameras_dict)

            timestamp_manager = self._open_cv_camera_manager.timestamp_manager

            try:
                if show_visualizer_gui:
                    self._visualizer_gui.setup_and_launch(self._open_cv_camera_manager.available_webcam_ids)

                should_continue = True
                while should_continue:  # BIG FRAME LOOP STARTS HERE

                    timestamp_manager.log_new_timestamp_for_main_loop_ns(time.perf_counter_ns())

                    if not self._open_cv_camera_manager.new_multi_frame_ready():
                        continue
                    this_multi_frame_payload = self._open_cv_camera_manager.latest_multi_frame

                    if this_multi_frame_payload is None:
                        continue

                    for this_webcam_id, this_open_cv_camera in connected_cameras_dict.items():

                        this_cam_latest_frame = this_multi_frame_payload.frames_dict[this_webcam_id]

                        if this_cam_latest_frame is None:
                            continue

                        image_to_display = this_cam_latest_frame.image.copy()
                        this_cam_this_frame_timestamp_ns = this_cam_latest_frame.timestamp

                        # log timestamp
                        this_cam_this_frame_timestamp_ns = this_cam_latest_frame.timestamp
                        this_cam_this_frame_number = this_cam_latest_frame.frame_number
                        timestamp_manager.log_new_timestamp_for_webcam_ns(this_webcam_id,
                                                                          this_cam_this_frame_timestamp_ns,
                                                                          this_cam_this_frame_number)

                        # # save this frame straight to the video file (no risk of memory overflow, but can't handle higher numbers of cameras)
                        # this_open_cv_camera.video_recorder.save_frame_to_video_file(this_cam_latest_frame)

                        # can handle large numbers of cameras, but will eventually fill up RAM and cause a crash
                        this_open_cv_camera.video_recorder.append_frame_payload_to_list(this_cam_latest_frame)

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
                            # self._visualizer_gui.update_timestamp_plots(timestamp_manager)

                            if self._visualizer_gui.shut_it_down:
                                logger.info("GUI closed.")
                                should_continue = False

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
                    this_open_cv_camera.video_recorder.save_frame_payload_list_to_disk()

                    if show_camera_views_in_windows:
                        logger.info(f"Destroy window {this_open_cv_camera.webcam_id_as_str}")
                        cv2.destroyWindow(this_open_cv_camera.webcam_id_as_str)

                if show_visualizer_gui:
                    self._visualizer_gui.close()

                timestamp_manager.create_diagnostic_plots()

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
        is_there_any_charuco_data = []
        for this_webcam_id in incoming_charuco_frame_data_per_camera_dict.keys():
            this_cam_data_list = incoming_charuco_frame_data_per_camera_dict[this_webcam_id]
            each_cam_number_of_frames.append(len(this_cam_data_list))
            this_cam_this_frame = this_cam_data_list[next_multi_frame_number]
            this_multi_frame_timestamps.append(this_cam_this_frame.raw_frame_payload.timestamp)
            this_multi_frame_charuco_data.append(this_cam_this_frame)
            is_there_any_charuco_data.append(this_cam_this_frame.charuco_view_data.some_charuco_corners_found)

        min_cameras_to_reconstruct = 2
        if sum(is_there_any_charuco_data) >= min_cameras_to_reconstruct:  # if at least 2 cameras have any data, then we can try to make some 3d dottos
            charuco2d_data_per_cam_dict = self.format_charuco2d_data(this_multi_frame_charuco_data)
            charuco_3d_data_payload = self._triangulate_2d_data(charuco2d_data_per_cam_dict,
                                                                self._charuco_board_detector.number_of_charuco_corners)

            x = charuco_3d_data_payload.data3d_trackedPointNum_xyz[:, 0]
            return charuco_3d_data_payload

    def _triangulate_2d_data(self, data2d_per_cam_dict: Dict,
                             number_of_tracked_points: int) -> Data3dSingleFramePayload:

        each_cam2d_data_list = [this_cam_charuco2d_frame_xy for this_cam_charuco2d_frame_xy in
                                data2d_per_cam_dict.values()]
        data2d_trackedPointNum_xyz_camNum = np.dstack(
            each_cam2d_data_list)  # stack lists (in depth) to make one numpy array with dimensions [number_of_tracked_points, XYZ, number_of_cameras]
        data2d_camNum_trackedPointNum_xy = data2d_trackedPointNum_xyz_camNum.reshape(self._number_of_cameras,
                                                                                     number_of_tracked_points,
                                                                                     2)  # reshape to fit into anipose (new dimensions [number_of_cameras, number_of_tracked_points, XYZ]

        # THIS IS WHERE THE MAGIC HAPPENS - 2d data from calibrated, synchronized cameras has now become a 3d estimate. Hurray! :`D
        data3d_trackedPointNum_xyz = self._anipose_camera_calibration_object.triangulate(
            data2d_camNum_trackedPointNum_xy,
            progress=True)

        # Reprojection error is a measure of the quality of the reconstruction. It is the distance (error) between the original 2d point and a reprojection of the 3d point back onto the image plane.
        # TODO - use this for filtering data (i.e. if one view has very high reprojection error, re-do the triangulation without that camera's view data)
        # TODO - we are currently using each tracking method's `confidence` values (or whatever they choose to call it) for thresholding, but it's problematic because of the neural_networks' propensity to apply high confidence to bonkers estimates, which leads to SPOOKY GHOST SKELETONS! :O
        data3d_trackedPointNum_reprojectionError = self._anipose_camera_calibration_object.reprojection_error(
            data3d_trackedPointNum_xyz,
            data2d_camNum_trackedPointNum_xy,
            mean=True)

        return Data3dSingleFramePayload(has_data=True,
                                        data3d_trackedPointNum_xyz=data3d_trackedPointNum_xyz,
                                        data3d_trackedPointNum_reprojectionError=data3d_trackedPointNum_reprojectionError, )

    def mediapipe_track_skeletons_offline(self):
        self._mediapipe2d_numCams_numFrames_numTrackedPoints_XY = self._mediapipe_skeleton_detector.process_session_folder(
            save_annotated_videos=True)


    def reconstruct3d_from_2d_data_offline(self):
        number_of_frames = self._mediapipe2d_numCams_numFrames_numTrackedPoints_XY.shape[1]
        number_of_tracked_points = self._mediapipe2d_numCams_numFrames_numTrackedPoints_XY.shape[2]
        number_of_spatial_dimensions = self._mediapipe2d_numCams_numFrames_numTrackedPoints_XY.shape[3]

        if not number_of_spatial_dimensions == 2:
            logger.error(f"This is supposed to be 2D data but, number_of_spatial_dimensions: {number_of_spatial_dimensions}")
            raise Exception

        # reshape data to collapse across 'frames' so it becomes [number_of_cameras, number_of_2d_points(numFrames*numPoints), XY]
        data2d_flat = self._mediapipe2d_numCams_numFrames_numTrackedPoints_XY.reshape(
            self._number_of_cameras,
            -1,
            2)

        logger.info(f"Reconstructing 3d points from 2d points with shape: "
                    f"number_of_cameras: {self._number_of_cameras},"
                    f" number_of_frames: {number_of_frames}, "
                    f" number_of_tracked_points: {number_of_tracked_points},"
                    f" number_of_spatial_dimensions: {number_of_spatial_dimensions}")

        data3d_flat = self._anipose_camera_calibration_object.triangulate(data2d_flat, progress=True)

        data3d_reprojectionError_flat = self._anipose_camera_calibration_object.reprojection_error(data3d_flat,
                                                                                        data2d_flat,
                                                                                        mean=True)

        data3d_numFrames_numTrackedPoints_XYZ = data3d_flat.reshape(number_of_frames, number_of_tracked_points, 3)
        data3d_numFrames_numTrackedPoints_reprojectionError = data3d_reprojectionError_flat.reshape(number_of_frames, number_of_tracked_points)

        self._save_mediapipe3d_data_to_npy(data3d_numFrames_numTrackedPoints_XYZ, data3d_numFrames_numTrackedPoints_reprojectionError)

        return Data3dFullSessionPayload(data3d_numFrames_numTrackedPoints_XYZ=data3d_numFrames_numTrackedPoints_XYZ,
                                        data3d_numFrames_numTrackedPoint_reprojectionError=data3d_numFrames_numTrackedPoints_reprojectionError)

    def _save_mediapipe3d_data_to_npy(self, data3d_numFrames_numTrackedPoints_XYZ:np.ndarray, data3d_numFrames_numTrackedPoints_reprojectionError:np.ndarray):
        output_data_folder = Path(get_output_data_folder_path(self._session_id))

        # save spatial XYZ data
        self._mediapipe_3dData_save_path = output_data_folder / "mediapipe_3dData_numFrames_numTrackedPoints_spatialXYZ.npy"
        logger.info(f"saving: {self._mediapipe_3dData_save_path}")
        np.save(str(self._mediapipe_3dData_save_path), data3d_numFrames_numTrackedPoints_XYZ)

        # save reprojection error
        self._mediapipe_reprojection_error_save_path = output_data_folder / "mediapipe_3dData_numFrames_numTrackedPoints_reprojectionError.npy"
        logger.info(f"saving: {self._mediapipe_reprojection_error_save_path}")
        np.save(str(self._mediapipe_reprojection_error_save_path), data3d_numFrames_numTrackedPoints_XYZ)



if __name__ == "__main__":
    print('running `session_pipeline_orchestrator` as `__main__')

    length_of_one_edge_of_a_black_square_on_the_charuco_board_in_mm = 39
    expected_framerate = 25

    calibrate_cameras = False

    this_session_orchestrator = SessionPipelineOrchestrator(expected_framerate=expected_framerate)

    if calibrate_cameras:
        this_session_orchestrator.calibrate_camera_capture_volume(
            charuco_square_size=length_of_one_edge_of_a_black_square_on_the_charuco_board_in_mm,
            pin_camera_0_to_origin=True)

    this_session_orchestrator.record_new_session()

    this_session_orchestrator.mediapipe_track_skeletons_offline()

    this_session_orchestrator.reconstruct3d_from_2d_data_offline()