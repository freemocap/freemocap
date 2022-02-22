import logging

import cv2
import mediapipe as mp

from src.cameras.cam_factory import create_opencv_cams


class MediapipeSkeletonDetection:
    async def process(self):
        logger = logging.getLogger(__name__)
        cv_cams = create_opencv_cams()

        for cv_cam in cv_cams:
            cv_cam.start_frame_capture()

        while True:
            exit_key = cv2.waitKey(1)
            if exit_key == 27:
                break
            for cv_cam in cv_cams:
                success, frame, timestamp = cv_cam.latest_frame()
                if not success:
                    logger.error("CV2 failed to grab a frame")
                    continue
                if frame is None:
                    logger.error("Frame is empty")
                    continue
                print(
                    f"got image of shape {frame.shape} from camera at port {cv_cam.webcam_id}"
                )

                image = self.detect_mediapipe_skeleton(frame)

                cv2.imshow(cv_cam.webcam_id_as_str, image)

    def detect_mediapipe_skeleton(self, image):
        # adapted from 'webcam' part of demo code here -
        # https://google.github.io/mediapipe/solutions/holistic.html

        mp_drawing = mp.solutions.drawing_utils
        mp_drawing_styles = mp.solutions.drawing_styles
        mp_holistic = mp.solutions.holistic

        # For webcam input:
        with mp_holistic.Holistic(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=0,
        ) as holistic:
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
            # Flip the image horizontally for a selfie-view display.
            # cv2.imshow('MediaPipe Holistic', cv2.flip(image, 1))

            return image
