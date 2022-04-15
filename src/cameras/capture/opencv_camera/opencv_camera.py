import logging
import platform
import time
import traceback

import cv2

from src.cameras.capture.dataclasses.frame_payload import FramePayload
from src.cameras.persistence.video_writer.video_recorder import VideoRecorder
from src.config.webcam_config import WebcamConfig
from src.cameras.capture.opencv_camera.camera_stream_thread_handler import VideoCaptureThread

logger = logging.getLogger(__name__)


class OpenCVCamera:
    """
    Performant implementation of video capture against webcams
    """
    def __init__(self, config: WebcamConfig, session_id: str = None):
        self._config = config
        self._name = f"Camera_{self._config.webcam_id}"
        self._opencv_video_capture_object: cv2.VideoCapture = None
        self._video_recorder: VideoRecorder = None
        self._running_thread: VideoCaptureThread = None
        self._new_frame_ready = False

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
    def webcam_id_as_str(self):
        return str(self._config.webcam_id)

    @property
    def current_fps(self):
        return self._running_thread.average_fps

    @property
    def is_capturing_frames(self):
        if not self._running_thread:
            logger.info("Frame Capture thread not running yet")
            return False
        return self._running_thread.is_capturing_frames

    @property
    def current_fps_short(self) -> str:
        return "{:.2f}".format(self._running_thread.average_fps)

    @property
    def latest_frame(self):
        self._new_frame_ready = False
        return self._running_thread.latest_frame

    def connect(self):
        if platform.system() == "Windows":
            cap_backend = cv2.CAP_DSHOW
        else:
            cap_backend = cv2.CAP_ANY

        self._opencv_video_capture_object = cv2.VideoCapture(
            self._config.webcam_id, cap_backend
        )
        self._apply_configuration()
        success, image = self._opencv_video_capture_object.read()

        if not success:
            logger.error(
                "Could not connect to a camera at port# {}".format(
                    self._config.webcam_id
                )
            )
            return success

        try:
            image_height = image.shape[0]
            image_width = image.shape[1]
            self._video_recorder = VideoRecorder(self._name,
                                                 image_width=image_width,
                                                 image_height=image_height)
        except:
            logger.error(f"could not create video recorder for image with shape (image_width={image_width}, image_height={image_height}) ")
            return False

        logger.debug(f"Camera found at port number {self._config.webcam_id}")
        fps_input_stream = int(self._opencv_video_capture_object.get(5))
        logger.debug("FPS of webcam hardware/input stream: {}".format(fps_input_stream))

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
            get_next_frame=self.get_next_frame,
        )

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

        if not self._opencv_video_capture_object.grab():
            return FramePayload(False, None, None)

        timestamp_ns = time.time_ns()
        success, image = self._opencv_video_capture_object.retrieve()

        self._new_frame_ready = success
        return FramePayload(success, image, timestamp_ns)

    def stop_frame_capture(self):
        self.close()

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
