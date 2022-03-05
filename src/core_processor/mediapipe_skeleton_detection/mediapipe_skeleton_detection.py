import logging
import os
import traceback
from pathlib import Path
from uuid import uuid4

import cv2
import mediapipe as mp

from src.cameras.cv_camera_manager import CVCameraManager
from src.cameras.dtos.create_writer_options import (
    CreateWriterOptions,
    get_canonical_time_str,
)
from src.core_processor.utils.image_fps_writer import write_fps_to_image

mp_holistic = mp.solutions.holistic
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

logger = logging.getLogger(__name__)


class MediapipeSkeletonDetection:
    def __init__(self, cam_manager: CVCameraManager):
        self._cam_manager = cam_manager

    async def process_as_frame_loop(self, webcam_id, cb, model_complexity: int = 1):
        timestr = get_canonical_time_str()
        options = CreateWriterOptions(
            filename_and_ext=f"{uuid4()}.{timestr}.avi",
            relative_folder_path=Path().joinpath("skeleton_detection"),
        )
        with self._cam_manager.start_capture_session_single_cam(
            webcam_id=webcam_id, create_writer_options=options
        ) as session_obj:
            with mp_holistic.Holistic(
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                model_complexity=model_complexity,
            ) as holistic:
                try:
                    while True:
                        image = self._process_single_cam_frame(
                            holistic, session_obj.cv_cam
                        )
                        session_obj.writer.write(image)
                        if cb and image is not None:
                            await cb(image)
                except Exception as e:
                    logger.error("Printing traceback")
                    traceback.print_exc()
                    raise e

    def process(self, model_complexity: int = 1):
        timestr = get_canonical_time_str()
        options = CreateWriterOptions(
            filename_and_ext=f"{uuid4()}.{timestr}.avi",
            parent_folder="skeleton_detection",
        )
        with self._cam_manager.start_capture_session_all_cams(options) as session_obj:
            with mp_holistic.Holistic(
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                model_complexity=model_complexity,
            ) as holistic:
                try:
                    while True:
                        exit_key = cv2.waitKey(1)
                        if exit_key == 27:
                            logger.info("ESC has been pressed.")
                            break
                        for response in session_obj:
                            cv_cam = response.cv_cam
                            writer = response.writer
                            image = self._process_single_cam_frame(holistic, cv_cam)
                            writer.write(image)
                            try:
                                cv2.imshow(cv_cam.webcam_id_as_str, image)
                            except:
                                logger.debug(
                                    "Failed to draw image for some reason for cv2.imshow"
                                )
                                traceback.print_exc()
                except:
                    logger.error("Printing traceback")
                    traceback.print_exc()
                finally:
                    for response in session_obj:
                        cv_cam = response.cv_cam
                        logger.info(f"Destroy window {cv_cam.webcam_id_as_str}")
                        cv2.destroyWindow(cv_cam.webcam_id_as_str)
                        cv2.waitKey(1)

    def _process_single_cam_frame(self, holistic, cv_cam):
        success, frame, timestamp = cv_cam.latest_frame
        if not success:
            # logger.error("CV2 failed to grab a frame")
            return
        if frame is None:
            logger.error("Frame is empty")
            return

        image = self.detect_mediapipe_skeleton(holistic, frame)
        write_fps_to_image(image, cv_cam.current_fps_short)
        return image

    def detect_mediapipe_skeleton(self, holistic, image):
        # adapted from 'webcam' part of demo code here -
        # https://google.github.io/mediapipe/solutions/holistic.html

        # For webcam input:
        # To improve performance, optionally mark the image as not writeable to
        # pass by reference.
        image.flags.writeable = False
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = holistic.process(image)

        # Draw landmark annotation on the image.
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        mp_drawing.draw_landmarks(
            image,
            results.face_landmarks,
            mp_holistic.FACEMESH_CONTOURS,
            landmark_drawing_spec=None,
            connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_contours_style(),
        )
        mp_drawing.draw_landmarks(
            image,
            results.pose_landmarks,
            mp_holistic.POSE_CONNECTIONS,
            landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style(),
        )
        return image


if __name__ == "__main__":
    MediapipeSkeletonDetection(CVCameraManager()).process()
