import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Union

import cv2
import mediapipe as mp
import numpy as np
from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder
from tqdm import tqdm

from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.mediapipe_skeleton_names_and_connections import (
    mediapipe_tracked_point_names_dict,
)
from freemocap.parameter_info_models.recording_processing_parameter_models import MediapipeParametersModel
from freemocap.system.paths_and_files_names import MEDIAPIPE_2D_NPY_FILE_NAME, ANNOTATED_VIDEOS_FOLDER_NAME, \
    MEDIAPIPE_POSE_WORLD_FILE_NAME

logger = logging.getLogger(__name__)


@dataclass
class Mediapipe2dNumpyArrays:
    body2d_frameNumber_trackedPointNumber_XY: np.ndarray = None
    body_pose_3d_frameNumber_trackedPointNumber_XYZ: np.ndarray = None
    rightHand3d_frameNumber_trackedPointNumber_XYZ: np.ndarray = None
    leftHand3d_frameNumber_trackedPointNumber_XYZ: np.ndarray = None
    face3d_frameNumber_trackedPointNumber_XYZ: np.ndarray = None

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

        if len(self.body2d_frameNumber_trackedPointNumber_XY.shape) == 3:  # multiple frames
            return np.hstack(
                [
                    self.body2d_frameNumber_trackedPointNumber_XY,
                    self.rightHand3d_frameNumber_trackedPointNumber_XYZ[:, :, :2],
                    self.leftHand3d_frameNumber_trackedPointNumber_XYZ[:, :, :2],
                    self.face3d_frameNumber_trackedPointNumber_XYZ[:, :, :2],
                ]
            )
        elif len(self.body2d_frameNumber_trackedPointNumber_XY.shape) == 2:  # single frame
            return np.vstack(
                [
                    self.body2d_frameNumber_trackedPointNumber_XY,
                    self.rightHand3d_frameNumber_trackedPointNumber_XYZ[:, :, :2],
                    self.leftHand3d_frameNumber_trackedPointNumber_XYZ[:, :, :2],
                    self.face3d_frameNumber_trackedPointNumber_XYZ[:, :, :2],
                ]
            )
        else:
            logger.error("data should have either 2 or 3 dimensions")


@dataclass
class Mediapipe2dDataPayload:
    raw_frame_payload: FramePayload = None
    mediapipe_results: Any = None
    annotated_image: np.ndarray = None
    pixel_data_numpy_arrays: Mediapipe2dNumpyArrays = None


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
        mediapipe_single_frame_npy_data.body2d_frameNumber_trackedPointNumber_XY = self._threshold_by_confidence(
            mediapipe_single_frame_npy_data.body2d_frameNumber_trackedPointNumber_XY,
            mediapipe_single_frame_npy_data.body2d_frameNumber_trackedPointNumber_confidence,
            confidence_threshold=0.5,
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
    ) -> (np.ndarray, np.ndarray):

        path_to_folder_of_videos_to_process = Path(path_to_folder_of_videos_to_process)

        logger.info(f"processing videos from: {path_to_folder_of_videos_to_process}")

        mediapipe2d_single_camera_npy_arrays_list = []
        for video_number, synchronized_video_file_path in enumerate(path_to_folder_of_videos_to_process.glob("*.mp4")):
            logger.info(f"Running `mediapipe` skeleton detection on  video: {str(synchronized_video_file_path)}")
            video_capture_object = cv2.VideoCapture(str(synchronized_video_file_path))

            video_width = video_capture_object.get(cv2.CAP_PROP_FRAME_WIDTH)
            video_height = video_capture_object.get(cv2.CAP_PROP_FRAME_HEIGHT)
            video_framerate = video_capture_object.get(cv2.CAP_PROP_FPS)

            video_mediapipe_results_list = []
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
                if not success or image is None:
                    logger.error(f"Failed to load an image from: {str(synchronized_video_file_path)}")
                    raise Exception

                mediapipe2d_data_payload = self.detect_skeleton_in_image(raw_image=image)
                video_mediapipe_results_list.append(mediapipe2d_data_payload.mediapipe_results)
                annotated_image = self._annotate_image(image, mediapipe2d_data_payload.mediapipe_results)
                video_annotated_images_list.append(annotated_image)

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

            camera_mediapipe_2d_single_camera_npy_arrays = self._list_of_mediapipe_results_to_npy_arrays(
                video_mediapipe_results_list,
                image_width=video_width,
                image_height=video_height,
            )

            mediapipe2d_single_camera_npy_arrays_list.append(camera_mediapipe_2d_single_camera_npy_arrays)

        all_cameras_data2d_list = [
            m2d.all_data2d_nFrames_nTrackedPts_XY for m2d in mediapipe2d_single_camera_npy_arrays_list
        ]

        all_cameras_pose_world_data_list = [
            m2d.body_pose_3d_frameNumber_trackedPointNumber_XYZ for m2d in mediapipe2d_single_camera_npy_arrays_list
        ]

        all_cameras_right_hand_world_data_list = [
            m2d.rightHand3d_frameNumber_trackedPointNumber_XYZ for m2d in mediapipe2d_single_camera_npy_arrays_list
        ]

        all_cameras_left_hand_world_data_list = [
            m2d.leftHand3d_frameNumber_trackedPointNumber_XYZ for m2d in mediapipe2d_single_camera_npy_arrays_list
        ]

        all_cameras_face_world_data_list = [
            m2d.face3d_frameNumber_trackedPointNumber_XYZ for m2d in mediapipe2d_single_camera_npy_arrays_list
        ]

        number_of_cameras = len(all_cameras_data2d_list)
        number_of_frames = all_cameras_data2d_list[0].shape[0]
        number_of_tracked_points = all_cameras_data2d_list[0].shape[1]
        number_of_spatial_dimensions = all_cameras_data2d_list[0].shape[2]  # XY, 2d data

        number_of_body_points = all_cameras_pose_world_data_list[0].shape[1]

        if not number_of_spatial_dimensions == 2:
            logger.error(f"this should be 2D data (XY pixel coordinates), but we founds {number_of_spatial_dimensions}")
            raise Exception

        data2d_numCams_numFrames_numTrackedPts_XY = np.empty(
            (
                number_of_cameras,
                number_of_frames,
                number_of_tracked_points,
                number_of_spatial_dimensions,
            )
        )

        data2d_pose_world_numCams_numFrames_numTrackedPts_XYZ = np.empty(
            (
                number_of_cameras,
                number_of_frames,
                number_of_tracked_points,
                3,
            )
        )

        for cam_num in range(number_of_cameras):
            data2d_numCams_numFrames_numTrackedPts_XY[cam_num, :, :, :] = all_cameras_data2d_list[cam_num]

            pose_3d = all_cameras_pose_world_data_list[cam_num]
            right_hand_3d = all_cameras_right_hand_world_data_list[cam_num]
            left_hand_3d = all_cameras_left_hand_world_data_list[cam_num]
            face_3d = all_cameras_face_world_data_list[cam_num]

            data2d_pose_world_numCams_numFrames_numTrackedPts_XYZ[cam_num, :, :, :] = np.concatenate((pose_3d,
                                                                                                      right_hand_3d,
                                                                                                      left_hand_3d,
                                                                                                      face_3d),
                                                                                                      axis=1)

            logger.info(f"The shape of data2d_pose_world_numCams_numFrames_numTrackedPts_XYZ is {data2d_pose_world_numCams_numFrames_numTrackedPts_XYZ.shape}")


        self._save_mediapipe2d_data_to_npy(
            data2d_numCams_numFrames_numTrackedPts_XY=data2d_numCams_numFrames_numTrackedPts_XY,
            data2d_pose_world_numCams_numFrames_numTrackedPts_XYZ=data2d_pose_world_numCams_numFrames_numTrackedPts_XYZ,
            output_data_folder_path=Path(output_data_folder_path),
        )
        return data2d_numCams_numFrames_numTrackedPts_XY, data2d_pose_world_numCams_numFrames_numTrackedPts_XYZ

    def _save_mediapipe2d_data_to_npy(self,
                                      data2d_numCams_numFrames_numTrackedPts_XY: np.ndarray,
                                      data2d_pose_world_numCams_numFrames_numTrackedPts_XYZ: np.ndarray,
                                      output_data_folder_path: Union[str, Path],
                                      ):
        mediapipe_2dData_save_path = Path(output_data_folder_path) / MEDIAPIPE_2D_NPY_FILE_NAME
        mediapipe_2dData_save_path.parent.mkdir(exist_ok=True, parents=True)
        logger.info(f"saving mediapipe 2d npy file: {mediapipe_2dData_save_path}")
        np.save(str(mediapipe_2dData_save_path), data2d_numCams_numFrames_numTrackedPts_XY)

        mediapipe_pose_world_save_path = Path(output_data_folder_path) / MEDIAPIPE_POSE_WORLD_FILE_NAME
        mediapipe_pose_world_save_path.parent.mkdir(exist_ok=True, parents=True)
        logger.info(f"saving mediapipe 3d npy xyz: {mediapipe_pose_world_save_path}")
        np.save(str(mediapipe_pose_world_save_path), data2d_pose_world_numCams_numFrames_numTrackedPts_XYZ)


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

        body_world_pose_3d_frameNumber_trackedPointNumber_XYZ = np.zeros(
            (
                number_of_frames,
                self.number_of_body_tracked_points,
                3,
            )
        )
        body_world_pose_3d_frameNumber_trackedPointNumber_XYZ[:] = np.nan

        body2d_frameNumber_trackedPointNumber_confidence = np.zeros(
            (number_of_frames, self.number_of_body_tracked_points)
        )
        body2d_frameNumber_trackedPointNumber_confidence[:] = np.nan  # only body markers get a 'confidence' value

        rightHand3d_frameNumber_trackedPointNumber_XYZ = np.zeros(
            (
                number_of_frames,
                self.number_of_right_hand_tracked_points,
                3,
            )
        )
        rightHand3d_frameNumber_trackedPointNumber_XYZ[:] = np.nan

        leftHand3d_frameNumber_trackedPointNumber_XYZ = np.zeros(
            (
                number_of_frames,
                self.number_of_left_hand_tracked_points,
                3,
            )
        )
        leftHand3d_frameNumber_trackedPointNumber_XYZ[:] = np.nan

        face3d_frameNumber_trackedPointNumber_XYZ = np.zeros(
            (
                number_of_frames,
                self.number_of_face_tracked_points,
                3,
            )
        )
        face3d_frameNumber_trackedPointNumber_XYZ[:] = np.nan

        all_body_tracked_points_visible_on_frame_bool_list = []
        all_right_hand_points_visible_on_frame_bool_list = []
        all_left_hand_points_visible_on_frame_bool_list = []
        all_face_points_visible_on_frame_bool_list = []
        all_tracked_points_visible_on_frame_list = []

        for frame_number, frame_results in enumerate(mediapipe_results_list):

            # get the Body data (aka 'pose')
            if frame_results.pose_landmarks is not None:

                for landmark_number, landmark_data in enumerate(frame_results.pose_landmarks.landmark):
                    body2d_frameNumber_trackedPointNumber_XY[frame_number, landmark_number, 0] = (
                            landmark_data.x * image_width
                    )
                    body2d_frameNumber_trackedPointNumber_XY[frame_number, landmark_number, 1] = (
                            landmark_data.y * image_height
                    )
                    body2d_frameNumber_trackedPointNumber_confidence[
                        frame_number, landmark_number
                    ] = landmark_data.visibility  # mediapipe calls their 'confidence' score 'visibility'

                for landmark_number, landmark_data in enumerate(frame_results.pose_landmarks.landmark):
                    body_world_pose_3d_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 0] = (
                            landmark_data.x * image_width
                    )
                    body_world_pose_3d_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 1] = (
                            landmark_data.y * image_width
                    )
                    body_world_pose_3d_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 2] = (
                            landmark_data.z * image_height
                    )

            # get Right Hand data
            if frame_results.right_hand_landmarks is not None:
                for landmark_number, landmark_data in enumerate(frame_results.right_hand_landmarks.landmark):
                    rightHand3d_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 0] = (
                            landmark_data.x * image_width
                    )
                    rightHand3d_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 1] = (
                            landmark_data.y * image_height
                    )
                    rightHand3d_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 2] = (
                            landmark_data.z * image_width
                    )

            # get Left Hand data
            if frame_results.left_hand_landmarks is not None:
                for landmark_number, landmark_data in enumerate(frame_results.left_hand_landmarks.landmark):
                    leftHand3d_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 0] = (
                            landmark_data.x * image_width
                    )
                    leftHand3d_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 1] = (
                            landmark_data.y * image_height
                    )
                    leftHand3d_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 2] = (
                            landmark_data.z * image_width
                    )

            # get Face data
            if frame_results.face_landmarks is not None:
                for landmark_number, landmark_data in enumerate(frame_results.face_landmarks.landmark):
                    face3d_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 0] = (
                            landmark_data.x * image_width
                    )
                    face3d_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 1] = (
                            landmark_data.y * image_height
                    )
                    face3d_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 2] = (
                            landmark_data.z * image_width
                    )

            # check if all tracked points are visible on this frame
            all_body_visible = all(sum(np.isnan(body2d_frameNumber_trackedPointNumber_XY[frame_number, :, :])) == 0)
            all_body_tracked_points_visible_on_frame_bool_list.append(all_body_visible)

            all_right_hand_visible = all(
                sum(np.isnan(rightHand3d_frameNumber_trackedPointNumber_XYZ[frame_number, :, :])) == 0
            )
            all_right_hand_points_visible_on_frame_bool_list.append(all_right_hand_visible)

            all_left_hand_visible = all(
                sum(np.isnan(leftHand3d_frameNumber_trackedPointNumber_XYZ[frame_number, :, :])) == 0
            )
            all_left_hand_points_visible_on_frame_bool_list.append(all_left_hand_visible)

            all_face_visible = all(sum(np.isnan(face3d_frameNumber_trackedPointNumber_XYZ[frame_number, :, :])) == 0)
            all_face_points_visible_on_frame_bool_list.append(all_face_visible)

            all_points_visible = all(
                [
                    all_body_visible,
                    all_right_hand_visible,
                    all_left_hand_visible,
                    all_face_visible,
                ],
            )

            all_tracked_points_visible_on_frame_list.append(all_points_visible)

        return Mediapipe2dNumpyArrays(
            body2d_frameNumber_trackedPointNumber_XY=np.squeeze(body2d_frameNumber_trackedPointNumber_XY),
            body_pose_3d_frameNumber_trackedPointNumber_XYZ=np.squeeze(body_world_pose_3d_frameNumber_trackedPointNumber_XYZ),
            rightHand3d_frameNumber_trackedPointNumber_XYZ=np.squeeze(rightHand3d_frameNumber_trackedPointNumber_XYZ),
            leftHand3d_frameNumber_trackedPointNumber_XYZ=np.squeeze(leftHand3d_frameNumber_trackedPointNumber_XYZ),
            face3d_frameNumber_trackedPointNumber_XYZ=np.squeeze(face3d_frameNumber_trackedPointNumber_XYZ),
            body2d_frameNumber_trackedPointNumber_confidence=np.squeeze(
                body2d_frameNumber_trackedPointNumber_confidence
            ),
        )

    def _threshold_by_confidence(
            self,
            data2d_trackedPoint_dim: np.ndarray,
            data2d_trackedPoint_confidence: np.ndarray,
            confidence_threshold: float,
    ):

        threshold_mask = data2d_trackedPoint_confidence < confidence_threshold
        data2d_trackedPoint_dim[threshold_mask, :] = np.nan
        return data2d_trackedPoint_dim
