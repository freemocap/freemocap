import logging
import multiprocessing
from pathlib import Path
from typing import List, Optional, Union, Callable, Tuple

import cv2
import mediapipe as mp
import numpy as np
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder
from tqdm import tqdm

from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.data_models.mediapipe_dataclasses import (
    Mediapipe2dNumpyArrays,
)
from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.data_models.mediapipe_skeleton_names_and_connections import (
    mediapipe_tracked_point_names_dict,
)
from freemocap.data_layer.recording_models.post_processing_parameter_models import MediapipeParametersModel
from freemocap.system.paths_and_filenames.file_and_folder_names import (
    MEDIAPIPE_2D_NPY_FILE_NAME,
    ANNOTATED_VIDEOS_FOLDER_NAME,
    MEDIAPIPE_BODY_WORLD_FILE_NAME,
)
from freemocap.utilities.get_video_paths import get_video_paths

logger = logging.getLogger(__name__)

mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
mp_holistic = mp.solutions.holistic

body_drawing_spec = mp_drawing.DrawingSpec(thickness=1, circle_radius=1)
hand_drawing_spec = mp_drawing.DrawingSpec(thickness=1, circle_radius=1)
face_drawing_spec = mp_drawing.DrawingSpec(thickness=1, circle_radius=1)


class MediaPipeSkeletonDetector:
    def __init__(
        self,
        parameter_model: Optional[MediapipeParametersModel] = None,
        use_tqdm: bool = True,
    ):
        if parameter_model is None:
            parameter_model = MediapipeParametersModel()

        self._parameter_model = parameter_model
        self._use_tqdm = use_tqdm
        self._mediapipe_payload_list = []

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

    def process_folder_full_of_videos(
        self,
        path_to_folder_of_videos_to_process: Union[Path, str],
        output_data_folder_path: Union[str, Path],
        kill_event: multiprocessing.Event = None,
        use_multiprocessing: bool = True,
    ) -> Union[np.ndarray, None]:
        path_to_folder_of_videos_to_process = Path(path_to_folder_of_videos_to_process)
        logger.info(f"processing videos from: {path_to_folder_of_videos_to_process}")

        tasks = self._create_video_processing_tasks(
            output_data_folder_path=output_data_folder_path,
            path_to_folder_of_videos_to_process=path_to_folder_of_videos_to_process,
        )

        if use_multiprocessing:
            with multiprocessing.Pool() as pool:
                mediapipe2d_single_camera_npy_arrays_list = pool.starmap(self.process_single_video, tasks)
        else:
            mediapipe2d_single_camera_npy_arrays_list = []
            for task in tasks:
                if kill_event is not None:
                    if kill_event.is_set():
                        break
                mediapipe2d_single_camera_npy_arrays_list.append(self.process_single_video(*task))

        (
            body_world_numCams_numFrames_numTrackedPts_XYZ,
            data2d_numCams_numFrames_numTrackedPts_XY,
        ) = self._build_output_numpy_array(mediapipe2d_single_camera_npy_arrays_list)

        self._save_mediapipe2d_data_to_npy(
            data2d_numCams_numFrames_numTrackedPts_XY=data2d_numCams_numFrames_numTrackedPts_XY,
            body_world_numCams_numFrames_numTrackedPts_XYZ=body_world_numCams_numFrames_numTrackedPts_XYZ,
            output_data_folder_path=Path(output_data_folder_path),
        )
        return data2d_numCams_numFrames_numTrackedPts_XY

    @staticmethod
    def process_single_video(
        synchronized_video_file_path: Path,
        output_data_folder_path: Path,
        mediapipe_parameters_model: MediapipeParametersModel,
        annotate_image: Callable,
        list_of_mediapipe_results_to_npy_arrays: Callable,
        use_tqdm: bool = True,
    ):
        logger.info(f"Running `mediapipe` skeleton detection on video: {str(synchronized_video_file_path)}")

        holistic_tracker = mp_holistic.Holistic(
            model_complexity=mediapipe_parameters_model.mediapipe_model_complexity,
            min_detection_confidence=mediapipe_parameters_model.min_detection_confidence,
            min_tracking_confidence=mediapipe_parameters_model.min_tracking_confidence,
        )

        video_capture_object = cv2.VideoCapture(str(synchronized_video_file_path))

        video_width = video_capture_object.get(cv2.CAP_PROP_FRAME_WIDTH)
        video_height = video_capture_object.get(cv2.CAP_PROP_FRAME_HEIGHT)
        video_framerate = video_capture_object.get(cv2.CAP_PROP_FPS)

        video_mediapipe_results_list = []
        video_annotated_images_list = []

        success, image = video_capture_object.read()

        number_of_frames = int(video_capture_object.get(cv2.CAP_PROP_FRAME_COUNT))

        if use_tqdm:
            iterator = tqdm(
                range(number_of_frames),
                desc=f"mediapiping video: {synchronized_video_file_path.name}",
                total=number_of_frames,
                colour="magenta",
                unit="frames",
                dynamic_ncols=True,
            )
        else:
            iterator = range(number_of_frames)

        for _frame_number in iterator:
            if not success or image is None:
                logger.error(f"Failed to load an image from: {str(synchronized_video_file_path)}")
                raise Exception

            mediapipe_results = holistic_tracker.process(
                image
            )  # <-this is where the magic happens, i.e. where the raw image is processed by a convolutional neural network to provide an estimate of joint position in pixel coordinates. Please don't forget that this is insane and should not be possible lol

            mediapipe_single_frame_npy_data = list_of_mediapipe_results_to_npy_arrays(
                [mediapipe_results],
                image_width=image.shape[0],
                image_height=image.shape[1],
            )

            confidence_threshold = 0.5

            threshold_mask = (
                mediapipe_single_frame_npy_data.body_frameNumber_trackedPointNumber_confidence < confidence_threshold
            )
            mediapipe_single_frame_npy_data.body_frameNumber_trackedPointNumber_XYZ[threshold_mask, :] = np.nan

            video_mediapipe_results_list.append(mediapipe_results)
            annotated_image = annotate_image(image, mediapipe_results)
            video_annotated_images_list.append(annotated_image)

            success, image = video_capture_object.read()

        try:
            annotated_video_path = output_data_folder_path.parent.parent / ANNOTATED_VIDEOS_FOLDER_NAME
            annotated_video_path.mkdir(exist_ok=True, parents=True)
            annotated_video_name = synchronized_video_file_path.stem + "_mediapipe.mp4"
            annotated_video_save_path = annotated_video_path / annotated_video_name

            logger.info(f"Saving mediapipe annotated video to : {annotated_video_save_path}")

            video_recorder = VideoRecorder()

            video_recorder.save_image_list_to_disk(
                image_list=video_annotated_images_list,
                path_to_save_video_file=annotated_video_save_path,
                frames_per_second=video_framerate,
            )
        except Exception as e:
            logger.error(f"Failed to save annotated video to disk: {e}")
            raise e

        camera_mediapipe_2d_single_camera_npy_arrays = list_of_mediapipe_results_to_npy_arrays(
            video_mediapipe_results_list,
            image_width=video_width,
            image_height=video_height,
        )

        # return the numpy array for this video
        return camera_mediapipe_2d_single_camera_npy_arrays

    def _build_output_numpy_array(self, mediapipe2d_single_camera_npy_arrays_list):
        all_cameras_data2d_list = [
            m2d.all_data2d_nFrames_nTrackedPts_XY for m2d in mediapipe2d_single_camera_npy_arrays_list
        ]
        all_cameras_pose_world_data_list = [
            m2d.body_world_frameNumber_trackedPointNumber_XYZ for m2d in mediapipe2d_single_camera_npy_arrays_list
        ]
        all_cameras_right_hand_world_data_list = [
            m2d.rightHand_frameNumber_trackedPointNumber_XYZ for m2d in mediapipe2d_single_camera_npy_arrays_list
        ]
        all_cameras_left_hand_world_data_list = [
            m2d.leftHand_frameNumber_trackedPointNumber_XYZ for m2d in mediapipe2d_single_camera_npy_arrays_list
        ]
        all_cameras_face_world_data_list = [
            m2d.face_frameNumber_trackedPointNumber_XYZ for m2d in mediapipe2d_single_camera_npy_arrays_list
        ]
        number_of_cameras = len(all_cameras_data2d_list)
        number_of_frames = all_cameras_data2d_list[0].shape[0]
        number_of_tracked_points = all_cameras_data2d_list[0].shape[1]
        number_of_spatial_dimensions = all_cameras_data2d_list[0].shape[2]
        number_of_body_points = all_cameras_pose_world_data_list[0].shape[1]  # noqa
        data2d_numCams_numFrames_numTrackedPts_XY = np.empty(
            (
                number_of_cameras,
                number_of_frames,
                number_of_tracked_points,
                number_of_spatial_dimensions,
            )
        )
        body_world_numCams_numFrames_numTrackedPts_XYZ = np.empty(
            (
                number_of_cameras,
                number_of_frames,
                number_of_tracked_points,
                number_of_spatial_dimensions,
            )
        )
        for cam_num in range(number_of_cameras):
            data2d_numCams_numFrames_numTrackedPts_XY[cam_num, :, :, :] = all_cameras_data2d_list[cam_num]

            pose_3d = all_cameras_pose_world_data_list[cam_num]
            right_hand_3d = all_cameras_right_hand_world_data_list[cam_num]
            left_hand_3d = all_cameras_left_hand_world_data_list[cam_num]
            face_3d = all_cameras_face_world_data_list[cam_num]

            body_world_numCams_numFrames_numTrackedPts_XYZ[cam_num, :, :, :] = np.concatenate(
                (pose_3d, right_hand_3d, left_hand_3d, face_3d), axis=1
            )

            logger.info(
                f"The shape of body_world_numCams_numFrames_numTrackedPts_XYZ is "
                f"{body_world_numCams_numFrames_numTrackedPts_XYZ.shape}"
            )
        return body_world_numCams_numFrames_numTrackedPts_XYZ, data2d_numCams_numFrames_numTrackedPts_XY

    def _create_video_processing_tasks(
        self,
        output_data_folder_path: Union[str, Path],
        path_to_folder_of_videos_to_process: Union[Path, str],
    ) -> List[Tuple]:
        video_paths = get_video_paths(path_to_folder_of_videos_to_process)
        tasks = [
            (
                video_path,
                output_data_folder_path,
                self._parameter_model,
                self._annotate_image,
                self._list_of_mediapipe_results_to_npy_arrays,
                self._use_tqdm,
            )
            for video_path in video_paths
        ]
        return tasks

    def _save_mediapipe2d_data_to_npy(
        self,
        data2d_numCams_numFrames_numTrackedPts_XY: np.ndarray,
        body_world_numCams_numFrames_numTrackedPts_XYZ: np.ndarray,
        output_data_folder_path: Union[str, Path],
    ):
        mediapipe_2dData_save_path = Path(output_data_folder_path) / MEDIAPIPE_2D_NPY_FILE_NAME
        mediapipe_2dData_save_path.parent.mkdir(exist_ok=True, parents=True)
        logger.info(f"saving mediapipe image npy file: {mediapipe_2dData_save_path}")
        np.save(str(mediapipe_2dData_save_path), data2d_numCams_numFrames_numTrackedPts_XY)

        mediapipe_body_world_save_path = Path(output_data_folder_path) / MEDIAPIPE_BODY_WORLD_FILE_NAME
        mediapipe_body_world_save_path.parent.mkdir(exist_ok=True, parents=True)
        logger.info(f"saving mediapipe body world npy xyz: {mediapipe_body_world_save_path}")
        np.save(str(mediapipe_body_world_save_path), body_world_numCams_numFrames_numTrackedPts_XYZ)

    @staticmethod
    def _annotate_image(image, mediapipe_results):
        mp_drawing.draw_landmarks(
            image=image,
            landmark_list=mediapipe_results.face_landmarks,
            connections=mp_holistic.FACEMESH_CONTOURS,
            landmark_drawing_spec=None,
            connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_contours_style(),
        )
        mp_drawing.draw_landmarks(
            image=image,
            landmark_list=mediapipe_results.face_landmarks,
            connections=mp_holistic.FACEMESH_TESSELATION,
            landmark_drawing_spec=None,
            connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style(),
        )
        mp_drawing.draw_landmarks(
            image=image,
            landmark_list=mediapipe_results.pose_landmarks,
            connections=mp_holistic.POSE_CONNECTIONS,
            landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style(),
        )
        mp_drawing.draw_landmarks(
            image=image,
            landmark_list=mediapipe_results.left_hand_landmarks,
            connections=mp_holistic.HAND_CONNECTIONS,
            landmark_drawing_spec=None,
            connection_drawing_spec=mp_drawing_styles.get_default_hand_connections_style(),
        )

        mp_drawing.draw_landmarks(
            image=image,
            landmark_list=mediapipe_results.right_hand_landmarks,
            connections=mp_holistic.HAND_CONNECTIONS,
            landmark_drawing_spec=None,
            connection_drawing_spec=mp_drawing_styles.get_default_hand_connections_style(),
        )
        return image

    def _list_of_mediapipe_results_to_npy_arrays(
        self,
        mediapipe_results_list: List,
        image_width: Union[int, float],
        image_height: Union[int, float],
    ) -> Mediapipe2dNumpyArrays:
        number_of_frames = len(mediapipe_results_list)
        number_of_spatial_dimensions = 3  # this will be 2d XY pixel data, with mediapipe's estimate of Z

        body_frameNumber_trackedPointNumber_XYZ = np.zeros(
            (
                number_of_frames,
                self.number_of_body_tracked_points,
                number_of_spatial_dimensions,
            )
        )
        body_frameNumber_trackedPointNumber_XYZ[:] = np.nan

        body_world_frameNumber_trackedPointNumber_XYZ = np.zeros(
            (
                number_of_frames,
                self.number_of_body_tracked_points,
                number_of_spatial_dimensions,
            )
        )
        body_world_frameNumber_trackedPointNumber_XYZ[:] = np.nan

        body_frameNumber_trackedPointNumber_confidence = np.zeros(
            (number_of_frames, self.number_of_body_tracked_points)
        )
        body_frameNumber_trackedPointNumber_confidence[:] = np.nan  # only body markers get a 'confidence' value

        rightHand_frameNumber_trackedPointNumber_XYZ = np.zeros(
            (
                number_of_frames,
                self.number_of_right_hand_tracked_points,
                number_of_spatial_dimensions,
            )
        )
        rightHand_frameNumber_trackedPointNumber_XYZ[:] = np.nan

        leftHand_frameNumber_trackedPointNumber_XYZ = np.zeros(
            (
                number_of_frames,
                self.number_of_left_hand_tracked_points,
                number_of_spatial_dimensions,
            )
        )
        leftHand_frameNumber_trackedPointNumber_XYZ[:] = np.nan

        face_frameNumber_trackedPointNumber_XYZ = np.zeros(
            (
                number_of_frames,
                self.number_of_face_tracked_points,
                number_of_spatial_dimensions,
            )
        )
        face_frameNumber_trackedPointNumber_XYZ[:] = np.nan

        all_body_tracked_points_visible_on_frame_bool_list = []
        all_right_hand_points_visible_on_frame_bool_list = []
        all_left_hand_points_visible_on_frame_bool_list = []
        all_face_points_visible_on_frame_bool_list = []
        all_tracked_points_visible_on_frame_list = []

        for frame_number, frame_results in enumerate(mediapipe_results_list):
            # get the Body data (aka 'pose')
            if frame_results.pose_landmarks is not None:
                for landmark_number, landmark_data in enumerate(frame_results.pose_landmarks.landmark):
                    body_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 0] = (
                        landmark_data.x * image_width
                    )
                    body_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 1] = (
                        landmark_data.y * image_height
                    )
                    body_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 2] = (
                        landmark_data.z
                        * image_width
                        # z is on roughly the same scale as x, according to mediapipe docs
                    )
                    body_frameNumber_trackedPointNumber_confidence[
                        frame_number, landmark_number
                    ] = landmark_data.visibility  # mediapipe calls their 'confidence' score 'visibility'

                for landmark_number, landmark_data in enumerate(frame_results.pose_world_landmarks.landmark):
                    body_world_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 0] = (
                        landmark_data.x * image_width
                    )
                    body_world_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 1] = (
                        landmark_data.y * image_height
                    )
                    body_world_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 2] = (
                        landmark_data.z * image_width
                    )

            # get Right Hand data
            if frame_results.right_hand_landmarks is not None:
                for landmark_number, landmark_data in enumerate(frame_results.right_hand_landmarks.landmark):
                    rightHand_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 0] = (
                        landmark_data.x * image_width
                    )
                    rightHand_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 1] = (
                        landmark_data.y * image_height
                    )
                    rightHand_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 2] = (
                        landmark_data.z * image_width
                    )

            # get Left Hand data
            if frame_results.left_hand_landmarks is not None:
                for landmark_number, landmark_data in enumerate(frame_results.left_hand_landmarks.landmark):
                    leftHand_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 0] = (
                        landmark_data.x * image_width
                    )
                    leftHand_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 1] = (
                        landmark_data.y * image_height
                    )
                    leftHand_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 2] = (
                        landmark_data.z * image_width
                    )

            # get Face data
            if frame_results.face_landmarks is not None:
                for landmark_number, landmark_data in enumerate(frame_results.face_landmarks.landmark):
                    face_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 0] = (
                        landmark_data.x * image_width
                    )
                    face_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 1] = (
                        landmark_data.y * image_height
                    )
                    face_frameNumber_trackedPointNumber_XYZ[frame_number, landmark_number, 2] = (
                        landmark_data.z * image_width
                    )

            # check if all tracked points are visible on this frame
            all_body_visible = all(sum(np.isnan(body_frameNumber_trackedPointNumber_XYZ[frame_number, :, :])) == 0)
            all_body_tracked_points_visible_on_frame_bool_list.append(all_body_visible)

            all_right_hand_visible = all(
                sum(np.isnan(rightHand_frameNumber_trackedPointNumber_XYZ[frame_number, :, :])) == 0
            )
            all_right_hand_points_visible_on_frame_bool_list.append(all_right_hand_visible)

            all_left_hand_visible = all(
                sum(np.isnan(leftHand_frameNumber_trackedPointNumber_XYZ[frame_number, :, :])) == 0
            )
            all_left_hand_points_visible_on_frame_bool_list.append(all_left_hand_visible)

            all_face_visible = all(sum(np.isnan(face_frameNumber_trackedPointNumber_XYZ[frame_number, :, :])) == 0)
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
            body_frameNumber_trackedPointNumber_XYZ=np.squeeze(body_frameNumber_trackedPointNumber_XYZ),
            body_world_frameNumber_trackedPointNumber_XYZ=np.squeeze(body_world_frameNumber_trackedPointNumber_XYZ),
            rightHand_frameNumber_trackedPointNumber_XYZ=np.squeeze(rightHand_frameNumber_trackedPointNumber_XYZ),
            leftHand_frameNumber_trackedPointNumber_XYZ=np.squeeze(leftHand_frameNumber_trackedPointNumber_XYZ),
            face_frameNumber_trackedPointNumber_XYZ=np.squeeze(face_frameNumber_trackedPointNumber_XYZ),
            body_frameNumber_trackedPointNumber_confidence=np.squeeze(body_frameNumber_trackedPointNumber_confidence),
        )
