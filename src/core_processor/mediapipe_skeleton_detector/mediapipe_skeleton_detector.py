import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

import cv2
import numpy as np
import mediapipe as mp
from rich.progress import Progress

from jon_scratch.opencv_camera import TweakedModel
from src.cameras.capture.dataclasses.frame_payload import FramePayload
from src.cameras.persistence.video_writer.video_recorder import VideoRecorder
from src.config.home_dir import get_session_path, get_synchronized_videos_path
logger = logging.getLogger(__name__)


class MediaPipeSkeletonDetector:
    def __init__(self, session_id: str = None):
        self._session_id = session_id
        self.model_complexity = 2  # can be 0,1, or 2 - higher numbers  are more accurate but heavier computationally
        self.min_detection_confidence = .5
        self.min_tracking_confidence = .5

        self._mediapipe_payload_list=[]

        self._mp_drawing = mp.solutions.drawing_utils
        self._mp_drawing_styles = mp.solutions.drawing_styles
        self._mp_holistic = mp.solutions.holistic

        self._body_drawing_spec = self._mp_drawing.DrawingSpec(thickness=1, circle_radius=1)
        self._hand_drawing_spec = self._mp_drawing.DrawingSpec(thickness=1, circle_radius=1)
        self._face_drawing_spec = self._mp_drawing.DrawingSpec(thickness=1, circle_radius=1)

        self._holistic_tracker = self._mp_holistic.Holistic(model_complexity=self.model_complexity,
                                                            min_detection_confidence=self.min_detection_confidence,
                                                            min_tracking_confidence=self.min_tracking_confidence)

    def detect_skeleton_in_image(self, raw_image, annotate_image=True):
        mediapipe_results = self._holistic_tracker.process(raw_image)  # <-this is where the magic happens
        annotated_image = None
        if annotate_image:
            annotated_image = self._annotate_image(raw_image, mediapipe_results)

        return MediapipeSkeletonPayload(mediapipe_results=mediapipe_results,
                                        annotated_image=annotated_image)

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

    def process_session_folder(self,
                               save_annotated_videos:bool=True):
        synchronized_videos_path = Path(get_synchronized_videos_path(self._session_id))

        for video_number, this_synchronized_video_file_path in enumerate(synchronized_videos_path.glob('*.mp4')):
            this_video_capture_object = cv2.VideoCapture(str(this_synchronized_video_file_path))
            logger.info(f"Running `mediapipe` skeleton detection on  video: {str(this_synchronized_video_file_path)}")
            this_video_mediapipe_payload_list = []

            success=True
            while success:
                success, image = this_video_capture_object.read()
                if image is None:
                    logger.error(f"Failed to load an image from: {str(this_synchronized_video_file_path)}")
                    raise Exception
                mediapipe_skeleton_payload = self.detect_skeleton_in_image(image, annotate_image=True)
                this_video_mediapipe_payload_list.append(mediapipe_skeleton_payload)

            if save_annotated_videos:
                self.save_annotated_videos(this_video_mediapipe_payload_list, this_video_capture_object, this_synchronized_video_file_path.stem)

    def save_annotated_videos(self, mediapipe_payload_list:List, video_capture_object:cv2.VideoCapture, video_file_name:str):

        this_video_name = video_file_name + "_mediapipe.mp4"
        image_width = video_capture_object.get(cv2.CAP_PROP_FRAME_WIDTH)
        image_height= video_capture_object.get(cv2.CAP_PROP_FRAME_HEIGHT)

        video_recorder = VideoRecorder(this_video_name,
                                       image_width,
                                       image_height,
                                       self._session_id,
                                       mediapipe_annotated_video_bool=True)

        image_list = [this_mediapipe_payload.annotated_image for this_mediapipe_payload in mediapipe_payload_list]
        logger.info(f'Saving mediapipe annotated video: {video_recorder.path_to_save_video_file}')
        video_recorder.save_image_list_to_disk(image_list, frame_rate=30)




class MediapipeSkeletonPayload(TweakedModel):
    mediapipe_results_list = List
    annotated_image = FramePayload
