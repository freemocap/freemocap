import asyncio
import logging
import platform
import time
import traceback

import cv2

from old_src.cameras.capture.dataclasses.frame_payload import FramePayload
from old_src.cameras.capture.opencv_camera.camera_stream_thread_handler import (
    VideoCaptureThread,
)
from old_src.cameras.viewer.cv_cam_viewer import CvCamViewer
from old_src.cameras.webcam_config import WebcamConfig

logger = logging.getLogger(__name__)


class OpenCVCamera:
    """
    Performant implementation of video start against webcams
    """

    def __init__(
        self,
        config: WebcamConfig,
        session_start_time_perf_counter_ns: int = 0,
        calibration_video_bool: bool = False,
    ):
        self._config = config
        self._name = f"Camera_{self._config.webcam_id}"
        self._opencv_video_capture_object: cv2.VideoCapture = None
        self._running_thread: VideoCaptureThread = None
        self._new_frame_ready = False
        self._number_of_frames_recorded = 0
        self._calibration_video_bool = calibration_video_bool
        self._session_start_time_perf_counter_ns = session_start_time_perf_counter_ns

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

    @property
    def is_open(self):
        return self._opencv_video_capture_object.isOpened()

    def connect(self):
        logger.info(f"Connecting to Camera: {self._config.webcam_id}...")

        if platform.system() == "Windows":
            logger.info(f"Windows machine detected - using backend `cv2.CAP_DSHOW`")
            cap_backend = cv2.CAP_DSHOW
        else:
            logger.info(f"Non-Windows machine detected - using backend `cv2.CAP_ANY`")
            cap_backend = cv2.CAP_ANY

        try:
            self.release()
        except:
            pass

        self._opencv_video_capture_object = cv2.VideoCapture(
            int(self._config.webcam_id), cap_backend
        )

        try:
            success, image = self._opencv_video_capture_object.read()
        except Exception as e:
            logger.error(
                f"Problem when trying to read frame from Camera: {self._config.webcam_id}"
            )
            traceback.print_exc()
            raise e

        if not success or image is None:
            logger.error(
                f"Failed to read frame from camera at port# {self._config.webcam_id}: "
                f"returned value: {success}, "
                f"returned image: {image}"
            )
            raise Exception

        self._apply_configuration()

        logger.info(f"Successfully connected to Camera: {self._config.webcam_id}!")
        return success

    def release(self):
        if self._opencv_video_capture_object is not None:
            logger.debug(
                f"Releasing `opencv_video_capture_object` for Camera: {self._config.webcam_id}"
            )
            self._opencv_video_capture_object.release()

        if self._running_thread.is_capturing_frames:
            logger.debug(
                f"Stopping frame capture thread for Camera: {self._config.webcam_id}"
            )
            self._running_thread.stop()

    def record_frames(self, save_frames_bool: bool):
        self._running_thread.is_recording_frames = save_frames_bool

    def start_frame_capture_thread(self):
        if self.is_capturing_frames:
            logger.debug(
                f"Already capturing frames for webcam_id: {self.webcam_id_as_str}"
            )
            return
        logger.info(f"Beginning frame start thread for webcam: {self.webcam_id_as_str}")
        self._running_thread = self._create_thread()
        self._running_thread.start()

    def _create_thread(self):
        logger.debug(f"Creating thread for webcam: {self.webcam_id_as_str}")
        return VideoCaptureThread(
            webcam_id=self.webcam_id_as_str,
            get_next_frame=self.get_next_frame,
        )

    def _apply_configuration(self):
        # set camera stream parameters
        logger.info(
            f"Applying configuration to Camera {self._config.webcam_id}:"
            f"Exposure: {self._config.exposure}, "
            f"Resolution width: {self._config.resolution_width}, "
            f"Resolution height: {self._config.resolution_height}, "
            f"Fourcc: {self._config.fourcc}"
        )
        try:
            if not self._opencv_video_capture_object.isOpened():
                logger.error(
                    f"Failed to apply configuration to Camera {self._config.webcam_id} - camera is not open"
                )
                return
        except Exception as e:
            logger.error(
                f"Failed when trying to check if Camera {self._config.webcam_id} is open"
            )
            return

        try:
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
        except Exception as e:
            logger.error(
                f"Problem applying configuration for camera: {self._config.webcam_id}"
            )
            traceback.print_exc()
            raise e

    def get_next_frame(self):

        try:
            #
            # uncomment above and below these calls to measure the time it takes to grab a frame
            #
            # timestamp_ns_pre = time.perf_counter_ns()

            ### Q - Why are we using `cv2.VideoCapture.grab();cv2.VideoCapture.retrieve();`  and not just `cv2.VideoCapture.read()`?
            ### A - see -> https://stackoverflow.com/questions/57716962/difference-between-video-capture-read-and-grab
            self._opencv_video_capture_object.grab()
            success, image = self._opencv_video_capture_object.retrieve()
            this_frame_timestamp_perf_counter_ns = (
                time.perf_counter_ns() - self._session_start_time_perf_counter_ns
            )

            # timestamp_ns_post = time.perf_counter_ns()
            # it_took_this_many_seconds_to_grab_the_frame = (timestamp_ns_post-timestamp_ns_pre)/1e9
        except:
            logger.error(f"Failed to read frame from Camera: {self.webcam_id_as_str}")
            raise Exception

        self._new_frame_ready = success

        if success:
            self._number_of_frames_recorded += 1
            # if self._camera_view_update_function is not None:
            #     self._camera_view_update_function(self.webcam_id_as_str, cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

        return FramePayload(
            success=success,
            image=image,
            timestamp_in_seconds_from_record_start=this_frame_timestamp_perf_counter_ns
            / 1e9,
            timestamp_unix_time_seconds=time.time(),
            frame_number=self.latest_frame_number,
            webcam_id=self.webcam_id_as_str,
        )

    def stop_frame_capture(self):
        self.close()

    async def show(self):
        viewer = CvCamViewer()
        viewer.begin_viewer(self.webcam_id_as_str)
        while True:
            if self.new_frame_ready:
                viewer.recv_img(self.latest_frame)
                await asyncio.sleep(0)

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
