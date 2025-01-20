import json
from dataclasses import dataclass, field

import cv2
import numpy as np

from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservations, CharucoObservation


@dataclass
class SingleCameraCalibrationError:
    mean_reprojection_error: float
    reprojection_error_by_view: list[float]
    jacobian: list[np.ndarray]


DEFAULT_INTRINSICS_COEFFICIENTS_COUNT = 5
MIN_CHARUCO_CORNERS = 6

@dataclass
class SingleCameraCalibrationEstimate:
    camera_matrix: np.ndarray[3, 3]
    distortion_coefficients: np.ndarray[..., 1]
    mean_reprojection_errors: list[float]
    camera_calibration_residuals: list[float]
    charuco_observations: CharucoObservations
    object_points_views: list[np.ndarray[..., 3]]
    image_points_views: list[np.ndarray[..., 2]]
    rotation_vectors: list[np.ndarray[..., 3]]
    translation_vectors: list[np.ndarray[..., 3]]
    reprojection_error_by_view: list[float]

    def to_serializable_dict(self  ):
        d =  {
            "camera_matrix": self.camera_matrix.tolist() if self.camera_matrix is not None else None,
            "distortion_coefficients": self.distortion_coefficients.tolist() if self.distortion_coefficients is not None else None,
            "mean_reprojection_errors": self.mean_reprojection_errors if self.mean_reprojection_errors else None,
            "camera_calibration_residuals": self.camera_calibration_residuals if self.camera_calibration_residuals else None,
            "charuco_observations": [obs.to_serializable_dict() for obs in self.charuco_observations] if self.charuco_observations else None,
            "object_points_views": [obj.tolist() for obj in self.object_points_views] if self.object_points_views else None,
            "image_points_views": [img.tolist() for img in self.image_points_views] if self.image_points_views else None,
            "rotation_vectors": [rot.tolist() for rot in self.rotation_vectors] if self.rotation_vectors else None,
            "translation_vectors": [trans.tolist() for trans in self.translation_vectors] if self.translation_vectors else None,
            "reprojection_error_by_view": self.reprojection_error_by_view if self.reprojection_error_by_view else None,
        }
        try:
            json.dumps(d).encode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to serialize SingleCameraCalibrationDTO to JSON: {e}")

@dataclass
class SingleCameraCalibrator:

    """
    SingleCameraCalibrator class for estimating camera calibration parameters.

    cv2.calibrateCamera docs: https://docs.opencv.org/4.10.0/d9/d0c/group__calib3d.html#ga687a1ab946686f0d85ae0363b5af1d7b

    Attributes:
        camera_matrix (np.ndarray[3, 3]): 3x3 matrix with rows: [focal_length_x, 0, center_point_x],
                                           [0, focal_length_y, center_point_y], [0, 0, 1]
        distortion_coefficients (np.ndarray[..., 1]): Distortion coefficients to include, e.g. [k1, k2, p1, p2, k3].
                                                      Can be 4, 5, 8, 12, or 14 elements.
        object_points_views (list[np.ndarray[..., 3]]): List of 3D points in the world (or object) coordinate space.
        image_points_views (list[np.ndarray[..., 2]]): List of 2D points in the image coordinate space (i.e. pixel coordinates).
        rotation_vectors (list[np.ndarray[..., 3]]): List of rotation vectors, containing the rotation of the camera
                                                     relative to the world coordinate space for each view.
        translation_vectors (list[np.ndarray[..., 3]]): List of translation vectors, containing the translation of the camera
                                                        relative to the world coordinate space for each view.
        error (SingleCameraCalibrationError | None): Calibration error details.
    """
    image_size: tuple[int, ...]

    charuco_corner_ids: list[int]
    charuco_corners_in_object_coordinates: np.ndarray[..., 3]

    aruco_marker_ids: list[int]
    aruco_corners_in_object_coordinates: list[np.ndarray[..., 3]]

    distortion_coefficients: np.ndarray[..., 1]
    camera_matrix: np.ndarray[3, 3]

    charuco_observations: CharucoObservations = field(default_factory=list)
    object_points_views: list[np.ndarray[..., 3]] = field(default_factory=list)
    image_points_views: list[np.ndarray[..., 2]] = field(default_factory=list)
    rotation_vectors: list[np.ndarray[..., 3]] = field(default_factory=list)
    translation_vectors: list[np.ndarray[..., 3]] = field(default_factory=list)
    reprojection_error_by_view:list[float] = field(default_factory=list)
    mean_reprojection_errors: list[float] = field(default_factory=list)
    camera_calibration_residuals: list[float] = field(default_factory=list)

    @property
    def has_calibration(self):
        return len(self.mean_reprojection_errors) > 0

    @classmethod
    def create_initial(cls,
                       image_size: tuple[int, ...],
                       aruco_marker_ids: list[int],
                       aruco_corners_in_object_coordinates: list[np.ndarray[..., 3]],
                       charuco_corner_ids: list[int],
                       charuco_corners_in_object_coordinates: np.ndarray[..., 3],
                       number_of_distortion_coefficients: int = DEFAULT_INTRINSICS_COEFFICIENTS_COUNT):
        camera_matrix = np.eye(3)
        camera_matrix[0, 2] = image_size[0] / 2  # x_center
        camera_matrix[1, 2] = image_size[1] / 2  # y_center


        if not number_of_distortion_coefficients in [4, 5, 8, 12, 14]:
            raise ValueError("Invalid number of distortion coefficients. Must be 4, 5, 8, 12, or 14.")

        if len(charuco_corner_ids) != charuco_corners_in_object_coordinates.shape[0]:
            raise ValueError("Number of charuco corner IDs must match the number of charuco corners.")
        if len(aruco_marker_ids) != len(aruco_corners_in_object_coordinates):
            raise ValueError("Number of aruco marker IDs must match the number of aruco corners.")

        return cls(image_size=image_size,
                   charuco_corner_ids=charuco_corner_ids,
                   charuco_corners_in_object_coordinates=charuco_corners_in_object_coordinates,
                   aruco_marker_ids=aruco_marker_ids,
                   aruco_corners_in_object_coordinates=aruco_corners_in_object_coordinates,
                   camera_matrix=camera_matrix,
                   distortion_coefficients=np.zeros(number_of_distortion_coefficients),
                   )


    def add_observation(self, observation: CharucoObservation):
        if observation.charuco_empty or len(observation.detected_charuco_corner_ids) < MIN_CHARUCO_CORNERS:
            return
        self._validate_observation(observation)

        self.charuco_observations.append(observation)
        self.image_points_views.append(np.squeeze(observation.detected_charuco_corners_image_coordinates))
        self.object_points_views.append(
            self.charuco_corners_in_object_coordinates[np.squeeze(observation.detected_charuco_corner_ids), :])


    def update_calibration_estimate(self):
        if len(self.object_points_views) < len(self.charuco_corner_ids):
            raise ValueError(f"You must have at least as many observations as charuco corners: "
                             f"#Current views: {len(self.object_points_views)}, "
                             f"#Charuco corners: {len(self.charuco_corner_ids)}")

        (residual,
         self.camera_matrix,
         self.distortion_coefficients,
         self.rotation_vectors,
         self.translation_vectors) = cv2.calibrateCamera(objectPoints=self.object_points_views,
                                                         imagePoints=self.image_points_views,
                                                         imageSize=self.image_size,
                                                         cameraMatrix=self.camera_matrix,
                                                         distCoeffs=self.distortion_coefficients,
                                                         )


        if not residual:
            raise ValueError(f"Camera Calibration failed! Check your input data:",
                             f"object_points_views: {self.object_points_views}",
                             f"image_points_views: {self.image_points_views}",
                             f"camera_matrix: {self.camera_matrix}",
                             f"distortion_coefficients: {self.distortion_coefficients}",
                             )
        self.camera_calibration_residuals.append(residual)
        self._update_reprojection_error()
        self._drop_suboptimal_views()

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
                                                                    cameraMatrix=self.camera_matrix,
                                                                    distCoeffs=self.distortion_coefficients)
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
                                 self.camera_matrix,
                                 self.distortion_coefficients,
                                 rotation_vector,
                                 translation_vector,
                                 axis_length)

    def _validate_observation(self, observation: CharucoObservation):
        if observation.image_size != self.image_size:
            raise ValueError("Image size mismatch")
        if any([corner_id not in self.charuco_corner_ids for corner_id in observation.detected_charuco_corner_ids]):
            raise ValueError(
                f"Invalid charuco corner ID detected: {observation.detected_charuco_corner_ids} not all in {self.charuco_corner_ids}")

    def _drop_suboptimal_views(self, ratio_to_keep: float = 0.5):
        if len(self.reprojection_error_by_view) < 2:
            return
        sorted_indices = np.argsort(self.reprojection_error_by_view)
        number_of_views_to_keep = int(len(sorted_indices) * ratio_to_keep)
        self.object_points_views = [self.object_points_views[i] for i in sorted_indices[:number_of_views_to_keep]]
        self.image_points_views = [self.image_points_views[i] for i in sorted_indices[:number_of_views_to_keep]]
        self.rotation_vectors = [self.rotation_vectors[i] for i in sorted_indices[:number_of_views_to_keep]]
        self.translation_vectors = [self.translation_vectors[i] for i in sorted_indices[:number_of_views_to_keep]]
        self.reprojection_error_by_view = [self.reprojection_error_by_view[i] for i in sorted_indices[:number_of_views_to_keep]]
        self.charuco_observations = [self.charuco_observations[i] for i in sorted_indices[:number_of_views_to_keep]]




    def _update_reprojection_error(self):
        if len(self.image_points_views) != len(self.object_points_views):
            raise ValueError("The number of image and object points must be the same")
        if len(self.image_points_views) == 0:
            raise ValueError("No image points provided")
        error = None
        jacobian = None
        self.reprojection_error_by_view = []
        for view_index in range(len(self.image_points_views)):
            projected_image_points, jacobian = cv2.projectPoints(self.object_points_views[view_index],
                                                                 self.rotation_vectors[view_index],
                                                                 self.translation_vectors[view_index],
                                                                 self.camera_matrix,
                                                                 self.distortion_coefficients)

            self.reprojection_error_by_view.append(np.mean(np.abs(self.image_points_views[view_index] - np.squeeze(projected_image_points))))

        self.mean_reprojection_errors.append(np.mean(self.reprojection_error_by_view) if self.reprojection_error_by_view else -1)

        print(f"Mean reprojection errors: {self.mean_reprojection_errors}")

    def to_dto(self) -> SingleCameraCalibrationEstimate:
        return SingleCameraCalibrationEstimate(
            camera_matrix=self.camera_matrix,
            distortion_coefficients=self.distortion_coefficients,
            mean_reprojection_errors=self.mean_reprojection_errors,
            camera_calibration_residuals=self.camera_calibration_residuals,
            charuco_observations=self.charuco_observations,
            object_points_views=self.object_points_views,
            image_points_views=self.image_points_views,
            rotation_vectors=self.rotation_vectors,
            translation_vectors=self.translation_vectors,
            reprojection_error_by_view=self.reprojection_error_by_view,
        )