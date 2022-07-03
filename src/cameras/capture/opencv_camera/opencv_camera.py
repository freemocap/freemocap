import asyncio
import logging
import platform
import time
import traceback
from typing import List, Union

import cv2

from src.cameras.capture.dataclasses.frame_payload import FramePayload
from src.cameras.persistence.video_writer.video_recorder import VideoRecorder
from src.cameras.viewer.cv_cam_viewer import CvCamViewer
from src.config.webcam_config import WebcamConfig
from src.cameras.capture.opencv_camera.camera_stream_thread_handler import VideoCaptureThread
from src.core_processor.timestamp_manager.timestamp_manager import TimestampLogger

logger = logging.getLogger(__name__)


class OpenCVCamera:
    """
    Performant implementation of video capture against webcams
    """

    def __init__(self,
                 config: WebcamConfig,
                 session_id: str = None,
                 timestamp_logger: TimestampLogger = None,
                 camera_view_update_function = None,
                 calibration_video_bool: bool = False):

        if timestamp_logger is None:
            self._timestamp_logger = TimestampLogger()
        else:
            self._timestamp_logger = timestamp_logger

        self._camera_view_update_function = camera_view_update_function

        self._config = config
        self._name = f"Camera_{self._config.webcam_id}"
        self._opencv_video_capture_object: cv2.VideoCapture = None
        self._video_recorder: VideoRecorder = None
        self._running_thread: VideoCaptureThread = None
        self._new_frame_ready = False
        self._number_of_frames_recorded = 0
        self._calibration_video_bool = calibration_video_bool
        self._session_id = session_id

    @property
    def session_id(self):
        if self._session_id is None:
            return False
        return self._session_id

    @property
    def new_frame_ready(self):
        """
        can be called to determine if the frame returned from  `self.latest_frame` is new or if it has been called before
        """
        return self._new_frame_ready

    @property
    def video_recorder(self):
        return self._video_recorder

    @property
    def name(self):
        return self._name

    @property
    def webcam_id_as_str(self) -> str:
        return str(self._config.webcam_id)

    @property
    def is_capturing_frames(self) -> bool:
        """Is the thread capturing frames from the cameras (but not necessarily recording them, that's handled by `self._running_thread.is_recording_frames`)"""
        if not self._running_thread:
            logger.info("Frame Capture thread not running yet")
            return False
        return self._running_thread.is_capturing_frames

    @property
    def latest_frame(self) -> FramePayload:
        self._new_frame_ready = False
        return self._running_thread.latest_frame

    @property
    def latest_frame_number(self):
        return self._number_of_frames_recorded

    @property
    def image_width(self):
        try:
            return int(self._opencv_video_capture_object.get(3))
        except Exception as e:
            raise e

    @property
    def image_height(self):
        try:
            return int(self._opencv_video_capture_object.get(4))
        except Exception as e:
            raise e

    def record_frames(self, save_frames_bool: bool):
        self._running_thread.is_recording_frames = save_frames_bool

    def connect(self):
        if platform.system() == "Windows":
            cap_backend = cv2.CAP_DSHOW
        else:
            cap_backend = cv2.CAP_ANY

        self._opencv_video_capture_object = cv2.VideoCapture(
            int(self._config.webcam_id), cap_backend
        )
        self._apply_configuration()
        success, image = self._opencv_video_capture_object.read()

        if not success or image is None:
            logger.error(
                "Could not connect to a camera at port# {}".format(
                    self._config.webcam_id
                )
            )
            raise Exception


        logger.debug(f"Camera found at port number {self._config.webcam_id}")
        fps_input_stream = int(self._opencv_video_capture_object.get(5))
        logger.debug("FPS of webcam hardware/input stream: {}".format(fps_input_stream))

        if self.session_id is False:
            logger.info(
                f"No `session_id` specified for {self._name}, video_recorder will not be created (because we won't know where to save the videos)")
            self._video_recorder = None
        else:
            image_height = image.shape[0]
            image_width = image.shape[1]

            self._video_recorder = VideoRecorder(self._name,
                                                 image_width=image_width,
                                                 image_height=image_height,
                                                 session_id=self.session_id,
                                                 calibration_video_bool=self._calibration_video_bool)

        return success

    def start_frame_capture_thread(self):
        if self.is_capturing_frames:
            logger.debug(
                f"Already capturing frames for webcam_id: {self.webcam_id_as_str}"
            )
            return
        logger.info(
            f"Beginning frame capture thread for webcam: {self.webcam_id_as_str}"
        )
        self._running_thread = self._create_thread()
        self._running_thread.start()

    def _create_thread(self):
        return VideoCaptureThread(
            webcam_id=self.webcam_id_as_str,
            get_next_frame=self.get_next_frame,
        )

    def _apply_configuration(self):
        # set camera stream parameters
        self._opencv_video_capture_object.set(
            cv2.CAP_PROP_EXPOSURE, self._config.exposure
        )
        self._opencv_video_capture_object.set(
            cv2.CAP_PROP_FRAME_WIDTH, self._config.resolution_width
        )
        self._opencv_video_capture_object.set(
            cv2.CAP_PROP_FRAME_HEIGHT, self._config.resolution_height
        )

        self._opencv_video_capture_object.set(
            cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self._config.fourcc)
        )

    def get_next_frame(self):

        # Why `grab()` not `read()`? see ->
        # https://stackoverflow.com/questions/57716962/difference-between-video-capture-read-and
        # -grab


        try:
            #
            # uncomment above and below these calls to measure the time it takes to grab a frame
            #
            # timestamp_ns_pre = time.perf_counter_ns()
            # timestamp_ns_pre = time.time_ns()
            if not self._opencv_video_capture_object.grab():
                return FramePayload(False, None, None)
            success, image = self._opencv_video_capture_object.retrieve()
            # timestamp_ns_post = time.time_ns()
            # timestamp_ns_post = time.perf_counter_ns()
            # it_took_this_many_seconds_to_grab_the_frame = (timestamp_ns_post-timestamp_ns_pre)/1e9
        except:
            logger.error(f"Failed to read frame from Camera: {self.webcam_id_as_str}")

        self._timestamp_logger.log_new_timestamp_perf_counter_ns(time.perf_counter_ns())

        latest_timestamp_in_seconds_from_record_start = self._timestamp_logger.latest_timestamp_in_seconds_from_record_start
        self._new_frame_ready = success

        if success:
            self._number_of_frames_recorded += 1
            if self._camera_view_update_function is not None:
                self._camera_view_update_function(self.webcam_id_as_str, cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

        return FramePayload(success=success,
                            image=image,
                            timestamp_in_seconds_from_record_start=latest_timestamp_in_seconds_from_record_start,
                            timestamp_unix_seconds = time.time_ns(),
                            frame_number=self.latest_frame_number,
                            webcam_id=self.webcam_id_as_str)

    def stop_frame_capture(self):
        self.close()

    def show(self):
        viewer = CvCamViewer()
        viewer.begin_viewer(self.webcam_id_as_str)
        while True:
            if self.new_frame_ready:
                viewer.recv_img(self.latest_frame)
                # await asyncio.sleep(0)

    def close(self):
        try:
            self._running_thread.stop()
            while self._running_thread.is_alive():
                # wait for thread to die.
                # TODO: use threading.Event for synchronize mainthread vs other threads
                time.sleep(0.1)
        except:
            logger.error("Printing traceback")
            traceback.print_exc()
        finally:
            logger.info("Closed {}".format(self._name))
            self._opencv_video_capture_object.release()
