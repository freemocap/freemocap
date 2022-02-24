import asyncio
import logging
import traceback

import cv2
import mediapipe as mp

from src.cameras.cam_factory import CVCameraManager, close_all_cameras
from src.core_processor.utils.image_fps_writer import write_fps_to_image

mp_holistic = mp.solutions.holistic
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

logger = logging.getLogger(__name__)


class MediapipeSkeletonDetection:
    async def process_as_frame_loop(self, cb):
        cam_manager: CVCameraManager = CVCameraManager()
        cv_cams = cam_manager.cv_cams

        with cam_manager.start_capture_session():
            with mp_holistic.Holistic(
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                model_complexity=0,
            ) as holistic:
                try:
                    while True:
                        for cv_cam in cv_cams:
                            image = self._process_single_cam_frame(holistic, cv_cam)
                            if cb:
                                await cb(image, cv_cam.webcam_id_as_str)
                except:
                    logger.error("Printing traceback")
                    traceback.print_exc()

    async def process(self):
        cam_manager: CVCameraManager = CVCameraManager()
        cv_cams = cam_manager.cv_cams

        with cam_manager.start_capture_session():
            with mp_holistic.Holistic(
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                model_complexity=0,
            ) as holistic:
                try:
                    while True:
                        exit_key = cv2.waitKey(1)
                        if exit_key == 27:
                            logger.info("ESC has been pressed.")
                            break
                        for cv_cam in cv_cams:
                            image = self._process_single_cam_frame(holistic, cv_cam)
                            cv2.imshow(cv_cam.webcam_id_as_str, image)
                except:
                    logger.error("Printing traceback")
                    traceback.print_exc()
                finally:
                    for cv_cam in cv_cams:
                        logger.info(f"Destroy window {cv_cam.webcam_id_as_str}")
                        cv2.destroyWindow(cv_cam.webcam_id_as_str)
                        cv2.waitKey(1)

    def _process_single_cam_frame(self, holistic, cv_cam):
        success, frame, timestamp = cv_cam.latest_frame
        if not success:
            logger.error("CV2 failed to grab a frame")
            return
        if frame is None:
            logger.error("Frame is empty")
            return

        image = self.detect_mediapipe_skeleton(holistic, frame)
        write_fps_to_image(image, cv_cam.current_fps)
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
    asyncio.run(MediapipeSkeletonDetection().process())
