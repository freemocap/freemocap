import logging

import cv2
import numpy as np

import cv2
import mediapipe as mp


from aiomultiprocess import Process
from aiomultiprocess.types import Queue

from src.core_processor.processor import ImagePayload


from rich import inspect


class MediapipeSkeletonDetection():
    async def create_new_process_for_run(self, queue: Queue):
        p = Process(target=self.process, args=(queue,))
        p.start()
        await p.join()

    async def process(self, queue: Queue):
        logger = logging.getLogger(__name__)
        while True:
            message = None
            try:
                message = queue.get(timeout=1)  # type: ImagePayload

            except Exception as e:
                pass


            if not message:
                print('No Message recieved!')
                continue

            frames = message.frames

            for f in frames:
                print(f'got image of shape {f.image.shape} from camera at port {f.port_number}, queueue size: {queue.qsize()}')

                image = self.detect_mediapipe_skeleton(f.image)
                # image = f.image
                text_to_write_on_this_camera = "image queueue size = " + str(queue.qsize())
                cv2.putText(
                    image,  # numpy array on which text is written
                    text_to_write_on_this_camera,  # text
                    (10,50),  # position at which writing has to start
                    cv2.FONT_HERSHEY_SIMPLEX,  # font family
                    .5,  # font size
                    (30, 10, 0, 255),  # font color
                    1)  # font stroke

                cv2.imshow(str(f.port_number), image)
                exit_key = cv2.waitKey(1)
                if exit_key == 27:
                    break


    def detect_mediapipe_skeleton(self, image):
        #adapted from 'webcam' part of demo code here - https://google.github.io/mediapipe/solutions/holistic.html


        mp_drawing = mp.solutions.drawing_utils
        mp_drawing_styles = mp.solutions.drawing_styles
        mp_holistic = mp.solutions.holistic

        # For webcam input:
        with mp_holistic.Holistic(
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                model_complexity=0) as holistic:

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
                connection_drawing_spec=mp_drawing_styles
                    .get_default_face_mesh_contours_style())
            mp_drawing.draw_landmarks(
                image,
                results.pose_landmarks,
                mp_holistic.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_drawing_styles
                    .get_default_pose_landmarks_style())
            # Flip the image horizontally for a selfie-view display.
            # cv2.imshow('MediaPipe Holistic', cv2.flip(image, 1))

            return image
