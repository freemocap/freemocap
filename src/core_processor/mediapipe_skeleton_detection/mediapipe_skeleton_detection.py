from dataclasses import dataclass

import numpy as np
import mediapipe as mp


class MediaPipeSkeletonDetection:

    def __init__(self,
                 model_complexity: int = 1,
                 min_detection_confidence: float = .5,
                 min_tracking_confidence: float = .5,
                 ):
        self.model_complexity = model_complexity     # can be 0,1, or 2 - higher numbers  are more accurate but heavier computationally
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self._mp_drawing = mp.solutions.drawing_utils
        self._mp_drawing_styles = mp.solutions.drawing_styles
        self._mp_holistic = mp.solutions.holistic

        self._body_drawing_spec = self._mp_drawing.DrawingSpec(thickness=1, circle_radius=.2)
        self._hand_drawing_spec = self._mp_drawing.DrawingSpec(thickness=1, circle_radius=.2)
        self._face_drawing_spec = self._mp_drawing.DrawingSpec(thickness=1, circle_radius=.2)

        self._holistic_tracker = self._mp_holistic.Holistic(model_complexity=self.model_complexity,
                                                            min_detection_confidence=self.min_detection_confidence,
                                                            min_tracking_confidence=self.min_tracking_confidence)

    def detect_skeleton_in_image(self, raw_image, annotate_image=True):
        mediapipe_results = self._holistic_tracker.process(raw_image)  # <-this is where the magic happens
        if annotate_image:
            return self._annotate_image(raw_image, mediapipe_results)

    def _annotate_image(self, image, mediapipe_results):
        self._mp_drawing.draw_landmarks(image=image,
                                        landmark_list=mediapipe_results.face_landmarks,
                                        connections=self._mp_holistic.FACEMESH_CONTOURS,
                                        landmark_drawing_spec=None,
                                        connection_drawing_spec=self._mp_drawing_styles
                                        .get_default_face_mesh_contours_style())
        self._mp_drawing.draw_landmarks(image=image,
                                        landmark_list=mediapipe_results.face_landmarks,
                                        connections=self._mp_holistic.FACEMESH_TESSELATION,
                                        landmark_drawing_spec=None,
                                        connection_drawing_spec=self._mp_drawing_styles
                                        .get_default_face_mesh_tesselation_style())
        self._mp_drawing.draw_landmarks(image=image,
                                        landmark_list=mediapipe_results.pose_landmarks,
                                        connections=self._mp_holistic.POSE_CONNECTIONS,
                                        landmark_drawing_spec=self._mp_drawing_styles
                                        .get_default_pose_landmarks_style())
        self._mp_drawing.draw_landmarks(
            image=image,
            landmark_list=mediapipe_results.left_hand_landmarks,
            connections=self._mp_holistic.HAND_CONNECTIONS,
            landmark_drawing_spec=None,
            connection_drawing_spec=self._mp_drawing_styles
                .get_default_hand_connections_style())

        self._mp_drawing.draw_landmarks(
            image=image,
            landmark_list=mediapipe_results.right_hand_landmarks,
            connections=self._mp_holistic.HAND_CONNECTIONS,
            landmark_drawing_spec=None,
            connection_drawing_spec=self._mp_drawing_styles
                .get_default_hand_connections_style())
        return image
