import logging
import time
import traceback
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np

from src.cameras.capture.frame_payload import FramePayload
from src.cameras.multicam_manager.cv_camera_manager import OpenCVCameraManager
from src.cameras.persistence.video_writer.video_writer import SaveOptions
from src.config.data_paths import create_home_data_directory
from src.core_processor.fps.fps_counter import FPSCamCounter
from src.core_processor.utils.image_fps_writer import write_fps_to_image

mp_holistic = mp.solutions.holistic
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

logger = logging.getLogger(__name__)


class ProcessResponse:
    frame_payload: FramePayload
    processed_image: Any

    def __init__(self, frame_payload: FramePayload, processed_image: np.array):
        self.frame_payload = frame_payload
        self.processed_image = processed_image


class MediapipeSkeletonDetection:
    def __init__(self, cam_manager: OpenCVCameraManager):
        self._cam_manager = cam_manager

    async def process_as_frame_loop(self, webcam_id, cb, model_complexity: int = 2):
        with self._cam_manager.start_capture_session_single_cam(
            webcam_id=webcam_id
        ) as session_obj:
            with mp_holistic.Holistic(
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                model_complexity=model_complexity,
            ) as holistic:
                try:
                    while True:
                        response = self._process_single_cam_frame(
                            holistic, session_obj.cv_cam
                        )
                        session_obj.writer.write(
                            FramePayload(
                                image=response.processed_image, timestamp=time.time_ns()
                            )
                        )
                        if cb and response.processed_image is not None:
                            await cb(response.processed_image)
                except Exception as e:
                    logger.error("Printing traceback")
                    traceback.print_exc()
                    raise e

    def process(self, model_complexity: int = 1):
        with self._cam_manager.start_capture_session_all_cams() as session_obj:
            fps_manager = FPSCamCounter(self._cam_manager.available_webcam_ids)
            with mp_holistic.Holistic(
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                model_complexity=model_complexity,
            ) as holistic:
                fps_manager.start_all()
                try:
                    while True:
                        exit_key = cv2.waitKey(1)
                        if exit_key == 27:
                            logger.info("ESC has been pressed.")
                            break
                        for response in session_obj:
                            cv_cam = response.cv_cam
                            writer = response.writer
                            response = self._process_single_cam_frame(holistic, cv_cam)
                            if not response:
                                continue
                            fps_manager.increment_frame_processed_for(
                                cv_cam.webcam_id_as_str
                            )
                            write_fps_to_image(
                                response.processed_image,
                                fps_manager.current_fps_for(cv_cam.webcam_id_as_str),
                            )
                            writer.write(
                                FramePayload(
                                    image=response.processed_image,
                                    timestamp=time.time_ns(),
                                )
                            )

                            cv2.imshow(
                                cv_cam.webcam_id_as_str, response.processed_image
                            )
                except:
                    logger.error("Printing traceback")
                    traceback.print_exc()
                finally:
                    for response in session_obj:
                        cv_cam = response.cv_cam
                        options = SaveOptions(
                            writer_dir=Path().joinpath(
                                cv_cam.session_writer_base_path,
                                "skeleton_detection",
                                f"webcam_{cv_cam.webcam_id_as_str}",
                            ),
                            fps=fps_manager.current_fps_for(cv_cam.webcam_id_as_str),
                            frame_width=cv_cam.image_width(),
                            frame_height=cv_cam.image_height(),
                        )
                        response.writer.save(options)
                        logger.info(f"Destroy window {cv_cam.webcam_id_as_str}")
                        cv2.destroyWindow(cv_cam.webcam_id_as_str)
                        cv2.waitKey(1)

    def _process_single_cam_frame(self, holistic, cv_cam):
        frame_payload = cv_cam.latest_frame
        if not frame_payload.success:
            return
        if frame_payload.image is None:
            return

        processed_image = self.detect_mediapipe_skeleton(holistic, frame_payload.image)
        return ProcessResponse(
            frame_payload=frame_payload, processed_image=processed_image
        )

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
        mp_drawing.draw_landmarks(
            image,
            results.left_hand_landmarks,
            mp_holistic.HAND_CONNECTIONS,
            landmark_drawing_spec=mp_drawing_styles.get_default_hand_landmarks_style(),
        )
        mp_drawing.draw_landmarks(
            image,
            results.right_hand_landmarks,
            mp_holistic.HAND_CONNECTIONS,
            landmark_drawing_spec=mp_drawing_styles.get_default_hand_landmarks_style(),
        )
        return image


if __name__ == "__main__":
    create_home_data_directory()
    MediapipeSkeletonDetection(OpenCVCameraManager()).process()
