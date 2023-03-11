import logging
import multiprocessing
from pathlib import Path
from typing import List, Union

import cv2
import mediapipe as mp
import numpy as np
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder
from tqdm import tqdm

from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.mediapipe2d_numpy_arrays import \
    Mediapipe2dNumpyArrays
from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.mediapipe_2d_data_payload import \
    Mediapipe2dDataPayload
from freemocap.system.paths_and_files_names import MEDIAPIPE_2D_NPY_FILE_NAME, ANNOTATED_VIDEOS_FOLDER_NAME
from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.mediapipe_skeleton_names_and_connections import (
    mediapipe_tracked_point_names_dict,
)
from freemocap.parameter_info_models.recording_processing_parameter_models import MediapipeParametersModel

logger = logging.getLogger(__name__)


class MediaPipeSkeletonDetector:
    def __init__(
            self,
            parameter_model=MediapipeParametersModel(),
    ):

        self._mediapipe_payload_list = []

        self._mp_drawing = mp.solutions.drawing_utils
        self._mp_drawing_styles = mp.solutions.drawing_styles
        self._mp_holistic = mp.solutions.holistic

        self._body_drawing_spec = self._mp_drawing.DrawingSpec(thickness=1, circle_radius=1)
        self._hand_drawing_spec = self._mp_drawing.DrawingSpec(thickness=1, circle_radius=1)
        self._face_drawing_spec = self._mp_drawing.DrawingSpec(thickness=1, circle_radius=1)

        self._holistic_tracker = self._mp_holistic.Holistic(
            model_complexity=parameter_model.model_complexity,
            min_detection_confidence=parameter_model.min_detection_confidence,
            min_tracking_confidence=parameter_model.min_tracking_confidence,
        )

        self._mediapipe_tracked_point_names_dict = mediapipe_tracked_point_names_dict

        self.body_names_list = self._mediapipe_tracked_point_names_dict["body"]
        self.right_hand_names_list = self._mediapipe_tracked_point_names_dict["right_hand"]
        self.left_hand_names_list = self._mediapipe_tracked_point_names_dict["left_hand"]
        self.face_names_list = self._mediapipe_tracked_point_names_dict["face"]

        # TODO - build a better iterator and list of `face_marker_names` that will only pull out the face_counters & iris edges (mp.python.solutions.face_mesh_connections.FACEMESH_CONTOURS, FACE_MESH_IRISES)

        self.number_of_body_tracked_points = len(self.body_names_list)
        self.number_of_right_hand_tracked_points = len(self.right_hand_names_list)
        self.number_of_left_hand_tracked_points = len(self.left_hand_names_list)
        self.number_of_face_tracked_points = mp.solutions.face_mesh.FACEMESH_NUM_LANDMARKS_WITH_IRISES

        self.number_of_tracked_points_total = (
                self.number_of_body_tracked_points
                + self.number_of_left_hand_tracked_points
                + self.number_of_right_hand_tracked_points
                + self.number_of_face_tracked_points
        )

    def detect_skeleton_in_image(
            self,
            raw_image: np.ndarray = None,
            annotated_image: np.ndarray = None,
    ) -> Mediapipe2dDataPayload:

        mediapipe_results = self._holistic_tracker.process(
            raw_image
        )  # <-this is where the magic happens, i.e. where the raw image is processed by a convolutional neural network to provide an estimate of joint position in pixel coordinates. Please don't forget that this is insane and should not be possible lol

        if annotated_image is None:
            annotated_image = raw_image.copy()

        annotated_image = self._annotate_image(annotated_image, mediapipe_results)

        mediapipe_single_frame_npy_data = self._list_of_mediapipe_results_to_npy_arrays(
            [mediapipe_results],
            image_width=annotated_image.shape[0],
            image_height=annotated_image.shape[1],
        )

        return Mediapipe2dDataPayload(
            mediapipe_results=mediapipe_results,
            annotated_image=annotated_image,
            pixel_data_numpy_arrays=mediapipe_single_frame_npy_data,
        )

    def process_folder_full_of_videos(
            self,
            path_to_folder_of_videos_to_process: Union[Path, str],
            output_data_folder_path: Union[str, Path],
            save_annotated_videos: bool = True,
            kill_event: multiprocessing.Event = None,
    ) -> Union[np.ndarray, None]:

        path_to_folder_of_videos_to_process = Path(path_to_folder_of_videos_to_process)

        logger.info(f"processing videos from: {path_to_folder_of_videos_to_process}")

        mediapipe_data_lists_by_video_number = {}
        for video_number, synchronized_video_file_path in enumerate(path_to_folder_of_videos_to_process.glob("*.mp4")):
            mediapipe_data_lists_by_video_number[video_number] = []

            logger.info(f"Running `mediapipe` skeleton detection on  video: {str(synchronized_video_file_path)}")
            video_capture_object = cv2.VideoCapture(str(synchronized_video_file_path))

            video_width = video_capture_object.get(cv2.CAP_PROP_FRAME_WIDTH)
            video_height = video_capture_object.get(cv2.CAP_PROP_FRAME_HEIGHT)
            video_framerate = video_capture_object.get(cv2.CAP_PROP_FPS)

            video_annotated_images_list = []

            success, image = video_capture_object.read()

            number_of_frames = int(video_capture_object.get(cv2.CAP_PROP_FRAME_COUNT))

            for frame_number in tqdm(
                    range(number_of_frames),
                    desc=f"mediapiping video: {synchronized_video_file_path.name}",
                    total=number_of_frames,
                    colour="magenta",
                    unit="frames",
                    dynamic_ncols=True,
            ):
                if kill_event is not None and kill_event.is_set():
                    logger.info("kill event received, exiting mediapipe process")
                    return

                if not success or image is None:
                    logger.error(f"Failed to load an image from: {str(synchronized_video_file_path)}")
                    raise Exception

                mediapipe2d_data_payload = self.detect_skeleton_in_image(raw_image=image)
                mediapipe_data_lists_by_video_number[video_number].append(
                    mediapipe2d_data_payload.pixel_data_numpy_arrays.all_data2d_nFrames_nTrackedPts_XY)
                video_annotated_images_list.append(
                    self._annotate_image(image, mediapipe2d_data_payload.mediapipe_results))

                success, image = video_capture_object.read()

            if save_annotated_videos:
                annotated_video_path = path_to_folder_of_videos_to_process.parent / ANNOTATED_VIDEOS_FOLDER_NAME
                annotated_video_path.mkdir(exist_ok=True, parents=True)
                annotated_video_name = synchronized_video_file_path.stem + "_mediapipe.mp4"
                annotated_video_save_path = annotated_video_path / annotated_video_name

                video_recorder = VideoRecorder()

                logger.info(f"Saving mediapipe annotated video to : {annotated_video_save_path}")
                video_recorder.save_image_list_to_disk(
                    image_list=video_annotated_images_list,
                    path_to_save_video_file=annotated_video_save_path,
                    frames_per_second=video_framerate,
                )

        data2d_numCams_numFrames_numTrackedPts_XY = np.asarray(list(mediapipe_data_lists_by_video_number.values()))

        if not data2d_numCams_numFrames_numTrackedPts_XY.shape[-1] == 2:
            logger.error(f"this should be 2D data (XY pixel coordinates), but we founds {data2d_numCams_numFrames_numTrackedPts_XY.shape[-1]}")
            raise Exception

        self._save_mediapipe2d_data_to_npy(
            data2d_numCams_numFrames_numTrackedPts_XY=data2d_numCams_numFrames_numTrackedPts_XY,
            output_data_folder_path=Path(output_data_folder_path),
        )
        return data2d_numCams_numFrames_numTrackedPts_XY

    def _save_mediapipe2d_data_to_npy(
            self,
            data2d_numCams_numFrames_numTrackedPts_XY: np.ndarray,
            output_data_folder_path: Union[str, Path],
    ):
        mediapipe_2dData_save_path = Path(output_data_folder_path) / MEDIAPIPE_2D_NPY_FILE_NAME
        mediapipe_2dData_save_path.parent.mkdir(exist_ok=True, parents=True)
        logger.info(f"saving: {mediapipe_2dData_save_path}")
        np.save(str(mediapipe_2dData_save_path), data2d_numCams_numFrames_numTrackedPts_XY)

        return mediapipe_2dData_save_path

    def _annotate_image(self, image, mediapipe_results):
        self._mp_drawing.draw_landmarks(
            image=image,
            landmark_list=mediapipe_results.face_landmarks,
            connections=self._mp_holistic.FACEMESH_CONTOURS,
            landmark_drawing_spec=None,
            connection_drawing_spec=self._mp_drawing_styles.get_default_face_mesh_contours_style(),
        )
        self._mp_drawing.draw_landmarks(
            image=image,
            landmark_list=mediapipe_results.face_landmarks,
            connections=self._mp_holistic.FACEMESH_TESSELATION,
            landmark_drawing_spec=None,
            connection_drawing_spec=self._mp_drawing_styles.get_default_face_mesh_tesselation_style(),
        )
        self._mp_drawing.draw_landmarks(
            image=image,
            landmark_list=mediapipe_results.pose_landmarks,
            connections=self._mp_holistic.POSE_CONNECTIONS,
            landmark_drawing_spec=self._mp_drawing_styles.get_default_pose_landmarks_style(),
        )
        self._mp_drawing.draw_landmarks(
            image=image,
            landmark_list=mediapipe_results.left_hand_landmarks,
            connections=self._mp_holistic.HAND_CONNECTIONS,
            landmark_drawing_spec=None,
            connection_drawing_spec=self._mp_drawing_styles.get_default_hand_connections_style(),
        )

        self._mp_drawing.draw_landmarks(
            image=image,
            landmark_list=mediapipe_results.right_hand_landmarks,
            connections=self._mp_holistic.HAND_CONNECTIONS,
            landmark_drawing_spec=None,
            connection_drawing_spec=self._mp_drawing_styles.get_default_hand_connections_style(),
        )
        return image

    def _list_of_mediapipe_results_to_npy_arrays(
            self,
            mediapipe_results_list: List,
            image_width: Union[int, float],
            image_height: Union[int, float],
    ) -> Mediapipe2dNumpyArrays:

        number_of_frames = len(mediapipe_results_list)
        number_of_spatial_dimensions = 2  # this will be 2d XY pixel data

        body2d_frameNumber_trackedPointNumber_XY = np.zeros(
            (
                number_of_frames,
                self.number_of_body_tracked_points,
                number_of_spatial_dimensions,
            )
        )
        body2d_frameNumber_trackedPointNumber_XY[:] = np.nan

        body2d_frameNumber_trackedPointNumber_confidence = np.zeros(
            (number_of_frames, self.number_of_body_tracked_points)
        )
        body2d_frameNumber_trackedPointNumber_confidence[:] = np.nan  # only body markers get a 'confidence' value

        rightHand2d_frameNumber_trackedPointNumber_XY = np.zeros(
            (
                number_of_frames,
                self.number_of_right_hand_tracked_points,
                number_of_spatial_dimensions,
            )
        )
        rightHand2d_frameNumber_trackedPointNumber_XY[:] = np.nan

        leftHand2d_frameNumber_trackedPointNumber_XY = np.zeros(
            (
                number_of_frames,
                self.number_of_left_hand_tracked_points,
                number_of_spatial_dimensions,
            )
        )
        leftHand2d_frameNumber_trackedPointNumber_XY[:] = np.nan

        face2d_frameNumber_trackedPointNumber_XY = np.zeros(
            (
                number_of_frames,
                self.number_of_face_tracked_points,
                number_of_spatial_dimensions,
            )
        )
        face2d_frameNumber_trackedPointNumber_XY[:] = np.nan

        for frame_number, frame_results in enumerate(mediapipe_results_list):

            # get the Body data (aka 'pose')
            if frame_results.pose_landmarks is not None:

                for landmark_number, landmark_data in enumerate(frame_results.pose_landmarks.landmark):

                    # skip data that is off screen
                    if landmark_data.x < 0 or landmark_data.y < 0:
                        continue
                    if landmark_data.x > 1 or landmark_data.y > 1:
                        continue

                    body2d_frameNumber_trackedPointNumber_XY[frame_number, landmark_number, 0] = (
                            landmark_data.x * image_width
                    )
                    body2d_frameNumber_trackedPointNumber_XY[frame_number, landmark_number, 1] = (
                            landmark_data.y * image_height
                    )
                    body2d_frameNumber_trackedPointNumber_confidence[
                        frame_number, landmark_number
                    ] = landmark_data.visibility  # mediapipe calls their 'confidence' score 'visibility'

            # get Right Hand data
            if frame_results.right_hand_landmarks is not None:
                for landmark_number, landmark_data in enumerate(frame_results.right_hand_landmarks.landmark):

                    # skip data that is off screen
                    if landmark_data.x < 0 or landmark_data.y < 0:
                        continue
                    if landmark_data.x > 1 or landmark_data.y > 1:
                        continue

                    rightHand2d_frameNumber_trackedPointNumber_XY[frame_number, landmark_number, 0] = (
                            landmark_data.x * image_width
                    )
                    rightHand2d_frameNumber_trackedPointNumber_XY[frame_number, landmark_number, 1] = (
                            landmark_data.y * image_height
                    )

            # get Left Hand data
            if frame_results.left_hand_landmarks is not None:
                for landmark_number, landmark_data in enumerate(frame_results.left_hand_landmarks.landmark):

                    # skip data that is off screen
                    if landmark_data.x < 0 or landmark_data.y < 0:
                        continue
                    if landmark_data.x > 1 or landmark_data.y > 1:
                        continue

                    leftHand2d_frameNumber_trackedPointNumber_XY[frame_number, landmark_number, 0] = (
                            landmark_data.x * image_width
                    )
                    leftHand2d_frameNumber_trackedPointNumber_XY[frame_number, landmark_number, 1] = (
                            landmark_data.y * image_height
                    )

            # get Face data
            if frame_results.face_landmarks is not None:
                for landmark_number, landmark_data in enumerate(frame_results.face_landmarks.landmark):

                    # skip data that is off screen
                    if landmark_data.x < 0 or landmark_data.y < 0:
                        continue
                    if landmark_data.x > 1 or landmark_data.y > 1:
                        continue

                    face2d_frameNumber_trackedPointNumber_XY[frame_number, landmark_number, 0] = (
                            landmark_data.x * image_width
                    )
                    face2d_frameNumber_trackedPointNumber_XY[frame_number, landmark_number, 1] = (
                            landmark_data.y * image_height
                    )

        return Mediapipe2dNumpyArrays(
            body2d_frameNumber_trackedPointNumber_XY=np.squeeze(body2d_frameNumber_trackedPointNumber_XY),
            rightHand2d_frameNumber_trackedPointNumber_XY=np.squeeze(rightHand2d_frameNumber_trackedPointNumber_XY),
            leftHand2d_frameNumber_trackedPointNumber_XY=np.squeeze(leftHand2d_frameNumber_trackedPointNumber_XY),
            face2d_frameNumber_trackedPointNumber_XY=np.squeeze(face2d_frameNumber_trackedPointNumber_XY),
            body2d_frameNumber_trackedPointNumber_confidence=np.squeeze(
                body2d_frameNumber_trackedPointNumber_confidence
            ),
        )
