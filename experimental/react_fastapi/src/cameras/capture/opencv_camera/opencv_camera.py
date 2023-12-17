import logging
import platform
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from pydantic import BaseModel

from src.cameras.capture.frame_payload import FramePayload
from src.cameras.capture.opencv_camera.frame_grabber import FrameThread
from src.core_processor.camera_calibration.lens_distortion_calibrator import LensDistortionCalibrationData

logger = logging.getLogger(__name__)


def _get_home_dir():
    return str(Path.home())


class WebcamConfig(BaseModel):
    webcam_id: int = 0
    exposure: int = -6
    resolution_width: int = 800
    resolution_height: int = 600
    save_video: bool = True
    # fourcc: str = "MP4V"
    fourcc: str = "MJPG"
    base_save_video_dir = _get_home_dir()


@dataclass
class CameraCalibrationData:
    image_width: int
    image_height: int
    lens_distortion_calibration_data: LensDistortionCalibrationData
    camera_translation_relative_to_camera0: np.ndarray
    camera_rotation_relative_to_camera0: np.ndarray

    def __init__(self, image_width: int, image_height: int):
        self.image_width = image_width
        self.image_height = image_height
        self.lens_distortion_calibration_data = LensDistortionCalibrationData(image_width, image_height)
        self.camera_translation_relative_to_camera0 = np.zeros((3, 1))
        self.camera_rotation_relative_to_camera0 = np.zeros((3, 1))


class OpenCVCamera:
    """
    Performant implementation of video capture against webcams
    """

    def __init__(self, config: WebcamConfig):
        self._config = config
        self._name = f"Camera {self._config.webcam_id}"
        self._opencv_video_capture_object: cv2.VideoCapture = None
        self._running_thread: FrameThread = None
        self._camera_calibration_data = None

    @property
    def camera_calibration_data(self):
        if self._camera_calibration_data is not None:
            return self._camera_calibration_data

        if self._camera_calibration_data is None and self.image_width is not None:
            self._camera_calibration_data = CameraCalibrationData(self.image_width, self.image_height)
            return self._camera_calibration_data

        logger.warning(
            'Can\'t request a cameras calibration info until the video capture is initialized and the image_width and image_height are known')

    @camera_calibration_data.setter
    def camera_calibration_data(self, camera_calibration_data: CameraCalibrationData):
        self._camera_calibration_data = camera_calibration_data

    @property
    def webcam_id_as_str(self):
        return str(self._config.webcam_id)

    @property
    def current_fps(self):
        return self._running_thread.current_fps

    @property
    def is_capturing_frames(self):
        if not self._running_thread:
            logger.error("Frame Capture thread not running yet")
            return False

        return self._running_thread.is_capturing_frames

    @property
    def current_fps_short(self) -> str:
        return "{:.2f}".format(self._running_thread.current_fps)

    @property
    def latest_frame(self):
        return self._running_thread.latest_frame

    @property
    def session_writer_base_path(self):
        return self._running_thread.session_writer_path

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
        logger.debug(f"Camera found at port number {self._config.webcam_id}")
        fps_input_stream = int(self._opencv_video_capture_object.get(5))
        logger.debug("FPS of webcam hardware/input stream: {}".format(fps_input_stream))

        return success

    def start_frame_capture(self):
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
        return FrameThread(
            webcam_id=self.webcam_id_as_str,
            get_next_frame=self.get_next_frame,
            save_video=self._config.save_video,
            frame_width=self.image_width,
            frame_height=self.image_height,
        )

    @property
    def image_width(self):
        try:
            return int(self._opencv_video_capture_object.get(3))
        except:
            return None

    @property
    def image_height(self):
        try:
            return int(self._opencv_video_capture_object.get(4))
        except:
            return None

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
        timestamp_ns_pre_grab = time.time_ns()
        # Why grab not read? see ->
        # https://stackoverflow.com/questions/57716962/difference-between-video-capture-read-and
        # -grab
        if not self._opencv_video_capture_object.grab():
            return FramePayload(False, None, None)

        timestamp_ns_post_grab = time.time_ns()
        timestamp_ns = (timestamp_ns_pre_grab + timestamp_ns_post_grab) / 2

        success, image = self._opencv_video_capture_object.retrieve()
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
