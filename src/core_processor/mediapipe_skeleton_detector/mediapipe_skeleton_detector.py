import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Union, Any

import cv2
import numpy as np
import mediapipe as mp

from jon_scratch.opencv_camera import TweakedModel
from src.cameras.capture.dataclasses.frame_payload import FramePayload
from src.cameras.persistence.video_writer.video_recorder import VideoRecorder
from src.config.home_dir import get_session_folder_path, get_synchronized_videos_folder_path, \
    get_session_output_data_folder_path
from src.core_processor.mediapipe_skeleton_detector.medaipipe_tracked_points_names_dict import \
    mediapipe_tracked_point_names_dict
from src.freemocap_qt_gui.refactored_gui.state.app_state import APP_STATE

logger = logging.getLogger(__name__)


@dataclass
class Mediapipe2dNumpyArrays:
    body2d_frameNumber_trackedPointNumber_XY: np.ndarray = None
    rightHand2d_frameNumber_trackedPointNumber_XY: np.ndarray = None
    leftHand2d_frameNumber_trackedPointNumber_XY: np.ndarray = None
    face2d_frameNumber_trackedPointNumber_XY: np.ndarray = None

    body2d_frameNumber_trackedPointNumber_confidence: np.ndarray = None

    @property
    def has_data(self):
        return not np.isnan(self.body2d_frameNumber_trackedPointNumber_XY).all()

    @property
    def all_data2d_nFrames_nTrackedPts_XY(self):
        """dimensions will be [number_of_frames , number_of_markers, XY]"""

        if self.body2d_frameNumber_trackedPointNumber_XY is None:
            # if there's no body data, there's no hand or face data either
            return

        if len(self.body2d_frameNumber_trackedPointNumber_XY.shape) == 3: #multiple frames
            return np.hstack([self.body2d_frameNumber_trackedPointNumber_XY,
                              self.rightHand2d_frameNumber_trackedPointNumber_XY,
                              self.leftHand2d_frameNumber_trackedPointNumber_XY,
                              self.face2d_frameNumber_trackedPointNumber_XY])
        elif len(self.body2d_frameNumber_trackedPointNumber_XY.shape) == 2: #single frame
            return np.vstack([self.body2d_frameNumber_trackedPointNumber_XY,
                              self.rightHand2d_frameNumber_trackedPointNumber_XY,
                              self.leftHand2d_frameNumber_trackedPointNumber_XY,
                              self.face2d_frameNumber_trackedPointNumber_XY])
        else:
            logger.error("data should have either 2 or 3 dimensions")



@dataclass
class Mediapipe2dDataPayload:
    raw_frame_payload: FramePayload = None
    mediapipe_results: Any = None
    annotated_image: np.ndarray = None
    pixel_data_numpy_arrays: Mediapipe2dNumpyArrays = None


class MediaPipeSkeletonDetector:
    def __init__(self, session_id: str = None):
        self._session_id = session_id
        self.model_complexity = 2  # can be 0,1, or 2 - higher numbers  are more accurate but heavier computationally
        self.min_detection_confidence = .5
        self.min_tracking_confidence = .5

        self._mediapipe_payload_list = []

        self._mp_drawing = mp.solutions.drawing_utils
        self._mp_drawing_styles = mp.solutions.drawing_styles
        self._mp_holistic = mp.solutions.holistic

        self._body_drawing_spec = self._mp_drawing.DrawingSpec(thickness=1, circle_radius=1)
        self._hand_drawing_spec = self._mp_drawing.DrawingSpec(thickness=1, circle_radius=1)
        self._face_drawing_spec = self._mp_drawing.DrawingSpec(thickness=1, circle_radius=1)

        self._holistic_tracker = self._mp_holistic.Holistic(model_complexity=self.model_complexity,
                                                            min_detection_confidence=self.min_detection_confidence,
                                                            min_tracking_confidence=self.min_tracking_confidence)
        self._mediapipe_tracked_point_names_dict = mediapipe_tracked_point_names_dict

        self.body_names_list = self._mediapipe_tracked_point_names_dict["body"]
        self.right_hand_names_list = self._mediapipe_tracked_point_names_dict["right_hand"]
        self.left_hand_names_list = self._mediapipe_tracked_point_names_dict["left_hand"]
        self.face_names_list = self._mediapipe_tracked_point_names_dict["face"]

        # TODO - build a better iterator and list of `face_marker_names` that will only pull out the face_counters & iris edges (mp.python.solutions.face_mesh_connections.FACEMESH_CONTOURS, FACE_MESH_IRISES)

        self.number_of_body_tracked_points = len(self.body_names_list)
        self.number_of_right_hand_tracked_points = len(self.right_hand_names_list)
        self.number_of_left_hand_tracked_points = len(self.left_hand_names_list)
        self.number_of_face_tracked_points = mp.python.solutions.face_mesh.FACEMESH_NUM_LANDMARKS_WITH_IRISES

        self.number_of_tracked_points_total = self.number_of_body_tracked_points + \
                                              self.number_of_left_hand_tracked_points + \
                                              self.number_of_right_hand_tracked_points + \
                                              self.number_of_face_tracked_points

    def detect_skeleton_in_image(self,
                                 raw_image: np.ndarray = None,
                                 raw_frame_payload: FramePayload = None,
                                 annotated_image: np.ndarray = None) -> Mediapipe2dDataPayload:

        if raw_frame_payload is not None:
            raw_image = raw_frame_payload.image.copy()

        mediapipe_results = self._holistic_tracker.process(
            raw_image)  # <-this is where the magic happens, i.e. where the raw image is processed by a convolutional neural network to provide an estimate of joint position in pixel coordinates. Please don't forget that this is insane and should not be possible lol

        if annotated_image is None:
            annotated_image = raw_image.copy()

        annotated_image = self._annotate_image(annotated_image, mediapipe_results)

        mediapipe_single_frame_npy_data = self._list_of_mediapipe_results_to_npy_arrays([mediapipe_results],
                                                                                        image_width=
                                                                                        annotated_image.shape[0],
                                                                                        image_height=
                                                                                        annotated_image.shape[1])
        mediapipe_single_frame_npy_data.body2d_frameNumber_trackedPointNumber_XY = self._threshold_by_confidence(
            mediapipe_single_frame_npy_data.body2d_frameNumber_trackedPointNumber_XY,
            mediapipe_single_frame_npy_data.body2d_frameNumber_trackedPointNumber_confidence,
            confidence_threshold=.5)

        return Mediapipe2dDataPayload(raw_frame_payload=raw_frame_payload,
                                      mediapipe_results=mediapipe_results,
                                      annotated_image=annotated_image,
                                      pixel_data_numpy_arrays=mediapipe_single_frame_npy_data)

    def process_session_folder(self,
                               save_annotated_videos: bool = True):
        synchronized_videos_path = Path(get_synchronized_videos_folder_path(self._session_id))
        logger.info(f"loading synchronized videos from: {synchronized_videos_path}")
        each_video_frame_width_list = []
        each_video_frame_height_list = []

        mediapipe2d_single_camera_npy_arrays_list = []
        for video_number, this_synchronized_video_file_path in enumerate(synchronized_videos_path.glob('*.mp4')):
            logger.info(f"Running `mediapipe` skeleton detection on  video: {str(this_synchronized_video_file_path)}")
            this_video_capture_object = cv2.VideoCapture(str(this_synchronized_video_file_path))

            this_video_width = this_video_capture_object.get(cv2.CAP_PROP_FRAME_WIDTH)
            this_video_height = this_video_capture_object.get(cv2.CAP_PROP_FRAME_HEIGHT)

            this_video_mediapipe_results_list = []
            this_video_annotated_images_list = []

            success, image = this_video_capture_object.read()
            if not success or image is None:
                logger.error(f"Failed to load an image from: {str(this_synchronized_video_file_path)}")
                raise Exception

            frame_number = 0
            while success and image is not None:

                frame_number+=1
                if frame_number%5==0:
                    print(f"frame {frame_number} out of {APP_STATE.number_of_frames_in_the_mocap_videos}")

                mediapipe2d_data_payload = self.detect_skeleton_in_image(raw_image=image)
                this_video_mediapipe_results_list.append(mediapipe2d_data_payload.mediapipe_results)
                annotated_image = self._annotate_image(image, mediapipe2d_data_payload.mediapipe_results)
                this_video_annotated_images_list.append(annotated_image)

                success, image = this_video_capture_object.read()

            if save_annotated_videos:
                self.save_annotated_videos(this_video_annotated_images_list,
                                           this_synchronized_video_file_path.stem,
                                           this_video_width,
                                           this_video_height,
                                           )

            this_camera_mediapipe_2d_single_camera_npy_arrays = self._list_of_mediapipe_results_to_npy_arrays(
                this_video_mediapipe_results_list,
                image_width=this_video_width,
                image_height=this_video_height)

            mediapipe2d_single_camera_npy_arrays_list.append(this_camera_mediapipe_2d_single_camera_npy_arrays)

        all_cameras_data2d_list = [m2d.all_data2d_nFrames_nTrackedPts_XY for m2d in
                                   mediapipe2d_single_camera_npy_arrays_list]

        number_of_cameras = len(all_cameras_data2d_list)
        number_of_frames = all_cameras_data2d_list[0].shape[0]
        number_of_tracked_points = all_cameras_data2d_list[0].shape[1]
        number_of_spatial_dimensions = all_cameras_data2d_list[0].shape[2]  # XY, 2d data

        if not number_of_spatial_dimensions == 2:
            logger.error(f"this should be 2D data (XY pixel coordinates), but we founds {number_of_spatial_dimensions}")
            raise Exception

        data2d_numCams_numFrames_numTrackedPts_XY = np.empty((number_of_cameras,
                                                              number_of_frames,
                                                              number_of_tracked_points,
                                                              number_of_spatial_dimensions))

        for this_cam_num in range(number_of_cameras):
            data2d_numCams_numFrames_numTrackedPts_XY[this_cam_num, :, :, :] = all_cameras_data2d_list[this_cam_num]

        self._save_mediapipe2d_data_to_npy(data2d_numCams_numFrames_numTrackedPts_XY)
        return data2d_numCams_numFrames_numTrackedPts_XY

    def _save_mediapipe2d_data_to_npy(self, data2d_numCams_numFrames_numTrackedPts_XY):
        output_data_folder = Path(get_session_output_data_folder_path(self._session_id))
        mediapipe_2dData_save_path = output_data_folder / "mediapipe_2dData_numCams_numFrames_numTrackedPoints_pixelXY.npy"
        logger.info(f"saving: {mediapipe_2dData_save_path}")
        np.save(str(mediapipe_2dData_save_path), data2d_numCams_numFrames_numTrackedPts_XY)

    def save_annotated_videos(self,
                              annotated_images_list: List[np.ndarray],
                              video_file_name: str,
                              image_width: Union[int, float],
                              image_height: Union[int, float],
                              ):

        this_video_name = video_file_name + "_mediapipe.mp4"

        video_recorder = VideoRecorder(this_video_name,
                                       image_width,
                                       image_height,
                                       self._session_id,
                                       mediapipe_annotated_video_bool=True)

        logger.info(f'Saving mediapipe annotated video: {this_video_name}')
        video_recorder.save_image_list_to_disk(annotated_images_list, frames_per_second=30)
        logger.info(f'mediapipe annotated video saved to: {video_recorder.path_to_save_video_file}')

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

    def _list_of_mediapipe_results_to_npy_arrays(self,
                                                 mediapipe_results_list: List,
                                                 image_width: Union[int, float],
                                                 image_height: Union[int, float],
                                                 ) -> Mediapipe2dNumpyArrays:

        # apparently `mediapipe_results.pose_landmarks.landmark` returns something iterable ¯\_(ツ)_/¯
        mediapipe_pose_landmark_iterator = mp.python.solutions.pose.PoseLandmark
        mediapipe_hand_landmark_iterator = mp.python.solutions.hands.HandLandmark

        number_of_frames = len(mediapipe_results_list)
        number_of_spatial_dimensions = 2  # this will be 2d XY pixel data

        body2d_frameNumber_trackedPointNumber_XY = np.zeros(
            (number_of_frames, self.number_of_body_tracked_points, number_of_spatial_dimensions))
        body2d_frameNumber_trackedPointNumber_XY[:] = np.nan

        body2d_frameNumber_trackedPointNumber_confidence = np.zeros(
            (number_of_frames, self.number_of_body_tracked_points))
        body2d_frameNumber_trackedPointNumber_confidence[:] = np.nan  # only body markers get a 'confidence' value

        rightHand2d_frameNumber_trackedPointNumber_XY = np.zeros((number_of_frames,
                                                                  self.number_of_right_hand_tracked_points,
                                                                  number_of_spatial_dimensions))
        rightHand2d_frameNumber_trackedPointNumber_XY[:] = np.nan

        leftHand2d_frameNumber_trackedPointNumber_XY = np.zeros((number_of_frames,
                                                                 self.number_of_left_hand_tracked_points,
                                                                 number_of_spatial_dimensions))
        leftHand2d_frameNumber_trackedPointNumber_XY[:] = np.nan

        face2d_frameNumber_trackedPointNumber_XY = np.zeros((number_of_frames,
                                                             self.number_of_face_tracked_points,
                                                             number_of_spatial_dimensions))
        face2d_frameNumber_trackedPointNumber_XY[:] = np.nan

        all_body_tracked_points_visible_on_this_frame_bool_list = []
        all_right_hand_points_visible_on_this_frame_bool_list = []
        all_left_hand_points_visible_on_this_frame_bool_list = []
        all_face_points_visible_on_this_frame_bool_list = []
        all_tracked_points_visible_on_this_frame_list = []

        for this_frame_number, this_frame_results in enumerate(mediapipe_results_list):

            # get the Body data (aka 'pose')
            if this_frame_results.pose_landmarks is not None:

                for this_landmark_number, this_landmark_data in enumerate(this_frame_results.pose_landmarks.landmark):
                    body2d_frameNumber_trackedPointNumber_XY[this_frame_number,
                                                             this_landmark_number,
                                                             0] = this_landmark_data.x * image_width
                    body2d_frameNumber_trackedPointNumber_XY[this_frame_number,
                                                             this_landmark_number,
                                                             1] = this_landmark_data.y * image_height
                    body2d_frameNumber_trackedPointNumber_confidence[this_frame_number,
                                                                     this_landmark_number] = this_landmark_data.visibility  # mediapipe calls their 'confidence' score 'visibility'

            # get Right Hand data
            if this_frame_results.right_hand_landmarks is not None:
                for this_landmark_number, this_landmark_data in enumerate(
                        this_frame_results.right_hand_landmarks.landmark):
                    rightHand2d_frameNumber_trackedPointNumber_XY[this_frame_number,
                                                                  this_landmark_number,
                                                                  0] = this_landmark_data.x * image_width
                    rightHand2d_frameNumber_trackedPointNumber_XY[this_frame_number,
                                                                  this_landmark_number,
                                                                  1] = this_landmark_data.y * image_height

            # get Left Hand data
            if this_frame_results.left_hand_landmarks is not None:
                for this_landmark_number, this_landmark_data in enumerate(
                        this_frame_results.left_hand_landmarks.landmark):
                    leftHand2d_frameNumber_trackedPointNumber_XY[this_frame_number,
                                                                 this_landmark_number,
                                                                 0] = this_landmark_data.x * image_width
                    leftHand2d_frameNumber_trackedPointNumber_XY[this_frame_number,
                                                                 this_landmark_number,
                                                                 1] = this_landmark_data.y * image_height

            # get Face data
            if this_frame_results.face_landmarks is not None:
                for this_landmark_number, this_landmark_data in enumerate(this_frame_results.face_landmarks.landmark):
                    face2d_frameNumber_trackedPointNumber_XY[this_frame_number, this_landmark_number,
                    0] = this_landmark_data.x * image_width
                    face2d_frameNumber_trackedPointNumber_XY[this_frame_number, this_landmark_number,
                    1] = this_landmark_data.y * image_height

            # check if all tracked points are visible on this frame
            all_body_visible = all(sum(
                np.isnan(body2d_frameNumber_trackedPointNumber_XY[this_frame_number, :, :])) == 0)
            all_body_tracked_points_visible_on_this_frame_bool_list.append(all_body_visible)

            all_right_hand_visible = all(sum(
                np.isnan(rightHand2d_frameNumber_trackedPointNumber_XY[this_frame_number, :, :])) == 0)
            all_right_hand_points_visible_on_this_frame_bool_list.append(all_right_hand_visible)

            all_left_hand_visible = all(sum(
                np.isnan(leftHand2d_frameNumber_trackedPointNumber_XY[this_frame_number, :, :])) == 0)
            all_left_hand_points_visible_on_this_frame_bool_list.append(all_left_hand_visible)

            all_face_visible = all(sum(
                np.isnan(face2d_frameNumber_trackedPointNumber_XY[this_frame_number, :, :])) == 0)
            all_face_points_visible_on_this_frame_bool_list.append(all_face_visible)

            all_points_visible = all([all_body_visible,
                                      all_right_hand_visible,
                                      all_left_hand_visible,
                                      all_face_visible],
                                     )

            all_tracked_points_visible_on_this_frame_list.append(all_points_visible)

        return Mediapipe2dNumpyArrays(
            body2d_frameNumber_trackedPointNumber_XY=np.squeeze(body2d_frameNumber_trackedPointNumber_XY),
            rightHand2d_frameNumber_trackedPointNumber_XY=np.squeeze(rightHand2d_frameNumber_trackedPointNumber_XY),
            leftHand2d_frameNumber_trackedPointNumber_XY=np.squeeze(leftHand2d_frameNumber_trackedPointNumber_XY),
            face2d_frameNumber_trackedPointNumber_XY=np.squeeze(face2d_frameNumber_trackedPointNumber_XY),
            body2d_frameNumber_trackedPointNumber_confidence=np.squeeze(
                body2d_frameNumber_trackedPointNumber_confidence))

    def _threshold_by_confidence(self,
                                 data2d_trackedPoint_dim: np.ndarray,
                                 data2d_trackedPoint_confidence: np.ndarray,
                                 confidence_threshold: float):

        threshold_mask = data2d_trackedPoint_confidence < confidence_threshold
        data2d_trackedPoint_dim[threshold_mask, :] = np.nan
        return data2d_trackedPoint_dim
