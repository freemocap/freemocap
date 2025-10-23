import logging

import cv2
import numpy as np
from pydantic import BaseModel, Field
from skellycam import CameraId
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservations, CharucoObservation, \
    AllCharucoCorners3DByIdInObjectCoordinates, AllArucoCorners3DByIdInObjectCoordinates

from freemocap.core.pipeline.tasks.calibration_task.calibration_helpers.calibration_numpy_types import ObjectPoints3D, \
    ImagePoints2D
from freemocap.core.pipeline.tasks.calibration_task.calibration_helpers.camera_math_models import RotationVector, TranslationVector, \
    TransformationMatrix, CameraDistortionCoefficients, CameraMatrix

logger = logging.getLogger(__name__)

DEFAULT_INTRINSICS_COEFFICIENTS_COUNT = 5
MIN_CHARUCO_CORNERS = 6


class CameraIntrinsicsEstimate(BaseModel):
    camera_id: CameraId
    camera_matrix: CameraMatrix
    distortion_coefficients: CameraDistortionCoefficients


class SingleCameraCalibrator(BaseModel):
    """
    SingleCameraCalibrator class for estimating camera calibration parameters.

    cv2.calibrateCamera docs: https://docs.opencv.org/4.10.0/d9/d0c/group__calib3d.html#ga687a1ab946686f0d85ae0363b5af1d7b
    """

    camera_id: CameraId
    image_size: tuple[int, ...]

    all_charuco_corner_ids: list[int]
    all_charuco_corners_in_object_coordinates: AllCharucoCorners3DByIdInObjectCoordinates

    all_aruco_marker_ids: list[int]
    all_aruco_corners_in_object_coordinates: AllArucoCorners3DByIdInObjectCoordinates

    distortion_coefficients: CameraDistortionCoefficients
    camera_matrix: CameraMatrix

    charuco_observations: CharucoObservations = Field(default_factory=CharucoObservations)
    object_points_views: list[ObjectPoints3D] = []
    image_points_views: list[ImagePoints2D] = []
    rotation_vectors: list[RotationVector] = []
    translation_vectors: list[TranslationVector] = []

    reprojection_error_per_point_by_view: list[list[float]] = []
    reprojection_error_by_view: list[float] = []
    mean_reprojection_error: float | None = None

    camera_calibration_residual: float | None = None


    @property
    def camera_intrinsics_estimate(self) -> CameraIntrinsicsEstimate:
        return CameraIntrinsicsEstimate(camera_id=self.camera_id,
                                        camera_matrix=self.camera_matrix,
                                        distortion_coefficients=self.distortion_coefficients)

    @property
    def has_calibration(self):
        return self.mean_reprojection_error is not None

    @property
    def charuco_transformation_matrices(self) -> list[TransformationMatrix]:
        return [TransformationMatrix.from_rotation_translation(rotation_vector=rotation_vector,
                                                               translation_vector=translation_vector)
                for rotation_vector, translation_vector in zip(self.rotation_vectors, self.translation_vectors)]

    @classmethod
    def create_initial(cls,
                       camera_id: CameraId,
                       image_size: tuple[int, ...],
                       all_aruco_marker_ids: list[int],
                       all_aruco_corners_in_object_coordinates: list[np.ndarray[..., 3]],
                       all_charuco_corner_ids: list[int],
                       all_charuco_corners_in_object_coordinates: np.ndarray[..., 3],
                       number_of_distortion_coefficients: int = DEFAULT_INTRINSICS_COEFFICIENTS_COUNT):

        if len(all_charuco_corner_ids) != all_charuco_corners_in_object_coordinates.shape[0]:
            raise ValueError("Number of charuco corner IDs must match the number of charuco corners.")
        if len(all_aruco_marker_ids) != len(all_aruco_corners_in_object_coordinates):
            raise ValueError("Number of aruco marker IDs must match the number of aruco corners.")

        return cls(camera_id=camera_id,
                   image_size=image_size,
                   all_charuco_corner_ids=all_charuco_corner_ids,
                   all_charuco_corners_in_object_coordinates=all_charuco_corners_in_object_coordinates,
                   all_aruco_marker_ids=all_aruco_marker_ids,
                   all_aruco_corners_in_object_coordinates=all_aruco_corners_in_object_coordinates,
                   camera_matrix=CameraMatrix.from_image_size(image_size=image_size),
                   distortion_coefficients=CameraDistortionCoefficients(
                       coefficients=np.zeros(number_of_distortion_coefficients))
                   )

    def add_observation(self, observation: CharucoObservation):
        if observation.frame_number in [obs.frame_number for obs in self.charuco_observations]:
            return
        if observation.charuco_empty or len(observation.detected_charuco_corner_ids) < MIN_CHARUCO_CORNERS:
            return
        self._validate_observation(observation)

        self.charuco_observations.append(observation)
        self.image_points_views.append(np.squeeze(observation.detected_charuco_corners_image_coordinates))
        self.object_points_views.append(
            self.all_charuco_corners_in_object_coordinates[np.squeeze(observation.detected_charuco_corner_ids), :])

    def update_calibration_estimate(self):

        if len(self.object_points_views) < len(self.all_charuco_corner_ids):
            raise ValueError(f"You must have at least as many observations as charuco corners: "
                             f"#Current views: {len(self.object_points_views)}, "
                             f"#Charuco corners: {len(self.all_charuco_corner_ids)}")

        # https://docs.opencv.org/4.10.0/d9/d0c/group__calib3d.html#ga687a1ab946686f0d85ae0363b5af1d7b
        (self.camera_calibration_residual,
         camera_matrix_output,
         distortion_coefficients_output,
         rotation_vectors_output,
         translation_vectors_output) = cv2.calibrateCamera(objectPoints=self.object_points_views,
                                                           imagePoints=self.image_points_views,
                                                           imageSize=self.image_size,
                                                           cameraMatrix=self.camera_matrix.matrix,  # will edit in place
                                                           distCoeffs=self.distortion_coefficients.coefficients,
                                                           # will edit in place
                                                           )

        if not self.camera_calibration_residual:
            raise ValueError(f"Camera Calibration failed! Check your input data:",
                             f"object_points_views: {self.object_points_views}",
                             f"image_points_views: {self.image_points_views}",
                             f"camera_matrix: {self.camera_matrix}",
                             f"distortion_coefficients: {self.distortion_coefficients}",
                             )
        self.rotation_vectors = [RotationVector(vector=np.squeeze(rotation_vector),
                                                reference_frame=f"camera-{self.camera_id}")
                                 for rotation_vector in rotation_vectors_output]
        self.translation_vectors = [TranslationVector(vector=np.squeeze(translation_vector),
                                                      reference_frame=f"camera-{self.camera_id}")
                                    for translation_vector in translation_vectors_output]

        self._update_reprojection_error()

    def get_board_pose(self, object_points: np.ndarray[..., 3], image_points: np.ndarray[..., 2]) -> tuple[
        np.ndarray[..., 3], np.ndarray[..., 3]]:
        if len(object_points) < 6:
            raise ValueError("You must have at least 4 object points to estimate the board pose.")
        if len(self.camera_calibration_residuals) == 0:
            raise ValueError("You must first calibrate the camera to get the board pose.")
        if len(object_points) != len(image_points):
            raise ValueError("The number of object and image points must be the same")
        success, rotation_vector, translation_vector = cv2.solvePnP(objectPoints=object_points,
                                                                    imagePoints=image_points,
                                                                    cameraMatrix=self.camera_matrix.matrix,
                                                                    distCoeffs=self.distortion_coefficients.coefficients, )
        if not success:
            raise ValueError(
                f"Failed to estimate board pose for object points: {object_points} and image points: {image_points}")
        return rotation_vector, translation_vector

    def draw_board_axes(self, image: np.ndarray, observation: CharucoObservation) -> np.ndarray:
        if len(self.camera_calibration_residuals) == 0:
            raise ValueError("You must first calibrate the camera to draw the board axes.")
        if observation.detected_charuco_corners_image_coordinates.shape[0] < 6:
            return image
        rotation_vector, translation_vector = self.get_board_pose(
            object_points=observation.detected_charuco_corners_in_object_coordinates,
            image_points=observation.detected_charuco_corners_image_coordinates
        )
        axis_length = 5
        return cv2.drawFrameAxes(image,
                                 self.camera_matrix.matrix,
                                 self.distortion_coefficients.coefficients,
                                 rotation_vector,
                                 translation_vector,
                                 axis_length)

    def _validate_observation(self, observation: CharucoObservation):
        if observation.image_size != self.image_size:
            raise ValueError("Image size mismatch")
        if any([corner_id not in self.all_charuco_corner_ids for corner_id in observation.detected_charuco_corner_ids]):
            raise ValueError(
                f"Invalid charuco corner ID detected: {observation.detected_charuco_corner_ids} not all in {self.all_charuco_corner_ids}")

    def _drop_suboptimal_views(self, ratio_to_keep: float = 0.5):
        if len(self.reprojection_error_by_view) < 2:
            return
        sorted_indices = np.argsort(self.reprojection_error_by_view)
        number_of_views_to_keep = int(len(sorted_indices) * ratio_to_keep)
        self.object_points_views = [self.object_points_views[i] for i in sorted_indices[:number_of_views_to_keep]]
        self.image_points_views = [self.image_points_views[i] for i in sorted_indices[:number_of_views_to_keep]]
        self.rotation_vectors = [self.rotation_vectors[i] for i in sorted_indices[:number_of_views_to_keep]]
        self.translation_vectors = [self.translation_vectors[i] for i in sorted_indices[:number_of_views_to_keep]]
        self.reprojection_error_by_view = [self.reprojection_error_by_view[i] for i in
                                           sorted_indices[:number_of_views_to_keep]]
        self.charuco_observations = [self.charuco_observations[i] for i in sorted_indices[:number_of_views_to_keep]]

    def _update_reprojection_error(self):
        # https://docs.opencv.org/4.10.0/d9/d0c/group__calib3d.html#ga1019495a2c8d1743ed5cc23fa0daff8c
        if len(self.image_points_views) != len(self.object_points_views):
            raise ValueError("The number of image and object points must be the same")
        if len(self.image_points_views) == 0:
            raise ValueError("No image points provided")
        self.reprojection_error_per_point_by_view = []
        self.reprojection_error_by_view = []
        for view_index in range(len(self.image_points_views)):
            projected_image_points, jacobian = cv2.projectPoints(objectPoints=self.object_points_views[view_index],
                                                                 rvec=self.rotation_vectors[view_index].vector,
                                                                 tvec=self.translation_vectors[view_index].vector,
                                                                 cameraMatrix=self.camera_matrix.matrix,
                                                                 distCoeffs=self.distortion_coefficients.coefficients,
                                                                 aspectRatio=self.image_size[0] / self.image_size[1]
                                                                 )

            self.reprojection_error_per_point_by_view.append(
                np.abs(self.image_points_views[view_index] - np.squeeze(projected_image_points)))

            self.reprojection_error_by_view.append(float(np.nanmean(self.reprojection_error_per_point_by_view[-1])))

        self.mean_reprojection_error = float(np.nanmean(self.reprojection_error_by_view))

        logger.debug(
            f"Camera {self.camera_id} -  Mean reprojection error: {self.mean_reprojection_error:.3f} pixels, reprojection error by view: {self.reprojection_error_by_view}")
