import logging

import cv2
import numpy as np
from pydantic import BaseModel, Field
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.charuco_tracker.charuco_observation import (
    CharucoObservations,
    BaseObservation,
    AllCharucoCorners3DByIdInObjectCoordinates,
    AllArucoCorners3DByIdInObjectCoordinates,
)

from freemocap.core.pipeline.realtime_pipeline.realtime_tasks.calibration_task.ooooold.calibration_helpers.calibration_numpy_types import (
    ObjectPoints3D,
    ImagePoints2D,
)
from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.calibration_helpers.camera_math_models import (
    RotationVector,
    TranslationVector,
    TransformationMatrix,
    CameraDistortionCoefficients,
    CameraMatrix,
)
from freemocap.core.pipeline.realtime_pipeline.realtime_tasks.calibration_task.ooooold.calibration_helpers.charuco_view_optimizer import (
    CharucoViewOptimizer,
    CharucoViewSelectionConfig,
)

logger = logging.getLogger(__name__)

DEFAULT_INTRINSICS_COEFFICIENTS_COUNT = 4
MIN_CHARUCO_CORNERS = 6
MIN_OBSERVATIONS_TO_CALIBRATE = 100
DEFAULT_TARGET_VIEW_COUNT = 25
INITIAL_VIEW_COUNT = 25


class CameraIntrinsicsEstimate(BaseModel):
    camera_id: CameraIdString
    camera_matrix: CameraMatrix
    distortion_coefficients: CameraDistortionCoefficients


class SingleCameraCalibrator(BaseModel):
    """
    SingleCameraCalibrator class for estimating camera calibration parameters.

    This calibrator stores ALL observations but can calibrate using a subset.
    The subset is determined by frame_numbers passed to update_calibration_estimate().
    """

    camera_id: CameraIdString
    image_size: tuple[int, ...]

    all_charuco_corner_ids: list[int]
    all_charuco_corners_in_object_coordinates: AllCharucoCorners3DByIdInObjectCoordinates

    all_aruco_marker_ids: list[int]
    all_aruco_corners_in_object_coordinates: AllArucoCorners3DByIdInObjectCoordinates

    distortion_coefficients: CameraDistortionCoefficients
    camera_matrix: CameraMatrix

    # Store ALL observations - never modified by optimization
    charuco_observations: CharucoObservations = Field(default_factory=CharucoObservations)

    # Calibration results - updated by update_calibration_estimate()
    board_rotation_vectors: list[RotationVector] = []
    board_translation_vectors: list[TranslationVector] = []
    reprojection_error_per_point_by_view: list[list[float]] = []
    reprojection_error_by_view: list[float] = []
    mean_reprojection_error: float | None = None
    camera_calibration_residual: float | None = None

    # Selected frame number for single-camera calibration (optimized coverage and diversity)
    selected_frame_numbers: list[int] = []

    @property
    def camera_intrinsics_estimate(self) -> CameraIntrinsicsEstimate:
        return CameraIntrinsicsEstimate(
            camera_id=self.camera_id,
            camera_matrix=self.camera_matrix,
            distortion_coefficients=self.distortion_coefficients,
        )

    @property
    def has_calibration(self) -> bool:
        return self.mean_reprojection_error is not None

    @property
    def ready_to_calibrate(self) -> bool:
        return len(self.charuco_observations) >= MIN_OBSERVATIONS_TO_CALIBRATE

    @property
    def charuco_transformation_matrices(self) -> list[TransformationMatrix]:
        return [
            TransformationMatrix.from_rotation_translation(
                rotation_vector=rotation_vector,
                translation_vector=translation_vector,
            )
            for rotation_vector, translation_vector in zip(
                self.board_rotation_vectors, self.board_translation_vectors
            )
        ]

    @classmethod
    def from_charuco_observations(
            cls,
            camera_id: CameraIdString,
            charuco_observations: CharucoObservations):
        calibrator = cls.from_charuco_observation(camera_id=camera_id,
                                                  charuco_observation=charuco_observations[0])
        for observation in charuco_observations[1:]:
            calibrator.add_observation(observation=observation)
        return calibrator

    @classmethod
    def from_charuco_observation(
            cls,
            camera_id: CameraIdString,
            charuco_observation: BaseObservation):

        return cls.create_initial(
            camera_id=camera_id,
            image_size=charuco_observation.image_size,
            all_aruco_marker_ids=charuco_observation.all_aruco_ids,
            all_aruco_corners_in_object_coordinates=charuco_observation.all_aruco_corners_in_object_coordinates,
            all_charuco_corner_ids=charuco_observation.all_charuco_ids,
            all_charuco_corners_in_object_coordinates=charuco_observation.all_charuco_corners_in_object_coordinates,
        )

    @classmethod
    def create_initial(
            cls,
            camera_id: CameraIdString,
            image_size: tuple[int, ...],
            all_aruco_marker_ids: list[int],
            all_aruco_corners_in_object_coordinates: AllArucoCorners3DByIdInObjectCoordinates,
            all_charuco_corner_ids: list[int],
            all_charuco_corners_in_object_coordinates: AllCharucoCorners3DByIdInObjectCoordinates,
            number_of_distortion_coefficients: int = DEFAULT_INTRINSICS_COEFFICIENTS_COUNT,
    ) -> "SingleCameraCalibrator":

        if len(all_charuco_corner_ids) != all_charuco_corners_in_object_coordinates.shape[0]:
            raise ValueError(
                "Number of charuco corner IDs must match the number of charuco corners."
            )
        if len(all_aruco_marker_ids) != len(all_aruco_corners_in_object_coordinates):
            raise ValueError(
                "Number of aruco marker IDs must match the number of aruco corners."
            )

        return cls(
            camera_id=camera_id,
            image_size=image_size,
            all_charuco_corner_ids=all_charuco_corner_ids,
            all_charuco_corners_in_object_coordinates=all_charuco_corners_in_object_coordinates,
            all_aruco_marker_ids=all_aruco_marker_ids,
            all_aruco_corners_in_object_coordinates=all_aruco_corners_in_object_coordinates,
            camera_matrix=CameraMatrix.from_image_size(image_size=image_size),
            distortion_coefficients=CameraDistortionCoefficients(
                coefficients=np.zeros(number_of_distortion_coefficients)
            ),
        )

    def add_observation(self, observation: BaseObservation) -> None:
        if observation.frame_number in [obs.frame_number for obs in self.charuco_observations]:
            return
        if observation.charuco_empty or len(observation.detected_charuco_corner_ids) < MIN_CHARUCO_CORNERS:
            return
        self._validate_observation(observation=observation)

        self.charuco_observations.append(observation)

    def calibrate(self) -> None:
        """
        Calibrate single-camera intrinsics using optimized subset of observations.

        """
        logger.info(f"Calibrating camera {self.camera_id} with {len(self.charuco_observations)} observations...")

        self.selected_frame_numbers = self.select_optimal_frame_numbers()

        logger.info(f"Calibrating camera {self.camera_id} with {len(self.selected_frame_numbers)} optimized views...")
        self.update_calibration_estimate(frame_numbers=self.selected_frame_numbers,
                                         store_results_in_state=True)

        logger.success(
            f"Camera {self.camera_id} calibration complete! "
            f"Calibration error: {self.mean_reprojection_error:.3f} pixels"
        )

    def select_optimal_frame_numbers(
            self,
            target_count: int = DEFAULT_TARGET_VIEW_COUNT,
            initial_count: int = DEFAULT_TARGET_VIEW_COUNT,
    ) -> list[int]:
        """
        Select optimal frame numbers for calibration without modifying stored observations.

        Uses two-stage optimization:
        1. Spatial optimization → quick calibration → pose estimation
        2. Pose-based optimization → return optimal frame numbers

        Args:
            target_count: Final number of views to select
            initial_count: Initial views for bootstrapping

        Returns:
            List of frame numbers to use for calibration
        """
        if len(self.charuco_observations) == 0:
            raise ValueError("No observations to optimize")

        original_count = len(self.charuco_observations)

        if original_count <= target_count:
            logger.info(
                f"Camera {self.camera_id}: Have {original_count} views, no optimization needed"
            )
            return [obs.frame_number for obs in self.charuco_observations]

        logger.info(
            f"Camera {self.camera_id}: Optimizing {original_count} views → {target_count} views"
        )

        # STAGE 1: Select initial views spatially
        config = CharucoViewSelectionConfig(
            initial_view_count=initial_count,
            target_view_count=target_count,
        )
        optimizer = CharucoViewOptimizer(
            image_size=(int(self.image_size[0]), int(self.image_size[1])),
            config=config,
        )

        initial_indices = optimizer.select_initial_views(observations=self.charuco_observations)
        initial_frame_numbers = [self.charuco_observations[i].frame_number for i in initial_indices]

        logger.info(f"Camera {self.camera_id}: Selected {len(initial_frame_numbers)} initial views, calibrating...")

        # Quick calibration for pose estimation
        (residual,
         camera_matrix,
         distortion_coefficients,
         rotation_vectors,
         translation_vectors
         ) = self.update_calibration_estimate(frame_numbers=initial_frame_numbers, store_results_in_state=False)

        # STAGE 2: Estimate poses for ALL observations
        logger.info(f"Camera {self.camera_id}: Estimating poses for all {original_count} observations...")

        all_rvecs = []
        all_tvecs = []

        for obs in self.charuco_observations:
            if obs.charuco_empty or len(obs.detected_charuco_corner_ids) < MIN_CHARUCO_CORNERS:
                all_rvecs.append(np.zeros(3, dtype=np.float32))
                all_tvecs.append(np.zeros(3, dtype=np.float32))
                continue

            object_points = self.all_charuco_corners_in_object_coordinates[
                np.squeeze(obs.detected_charuco_corner_ids), :
            ]
            image_points = np.squeeze(obs.detected_charuco_corners_image_coordinates)

            try:
                success, rvec, tvec = cv2.solvePnP(
                    objectPoints=object_points,
                    imagePoints=image_points,
                    cameraMatrix=camera_matrix,
                    distCoeffs=distortion_coefficients,
                )
                if not success:
                    raise ValueError(f"solvePnP failed for frame {obs.frame_number}")

                all_rvecs.append(np.squeeze(rvec))
                all_tvecs.append(np.squeeze(tvec))
            except (cv2.error, ValueError) as e:
                raise RuntimeError(f"Failed to estimate pose for frame {obs.frame_number}: {e}")

        # Select final views using pose information
        final_indices = optimizer.select_final_views(
            observations=self.charuco_observations,
            rotation_vectors=all_rvecs,
            translation_vectors=all_tvecs,
        )

        final_frame_numbers = [self.charuco_observations[i].frame_number for i in final_indices]

        logger.info(
            f"Camera {self.camera_id}: Optimization complete - "
            f"selected {len(final_frame_numbers)} final views"
        )

        return final_frame_numbers

    def update_calibration_estimate(
            self,
            frame_numbers: list[int] | None = None,
            store_results_in_state: bool = True  # if false, don't update internal state
    ) -> tuple[float, np.ndarray, np.ndarray, list[RotationVector], list[TranslationVector]]:
        """
        Update calibration estimate using specified frame numbers.

        If frame_numbers is None, uses ALL observations.

        Args:
            frame_numbers: Specific frame numbers to use for calibration.
                          If None, uses all available observations.
        """
        # Select observations to use
        if frame_numbers is None:
            observations_to_use = self.charuco_observations
            logger.info(f"Calibrating camera {self.camera_id} with ALL {len(observations_to_use)} observations")
        else:
            frame_number_set = set(frame_numbers)
            observations_to_use = [
                obs for obs in self.charuco_observations
                if obs.frame_number in frame_number_set
            ]

            if len(observations_to_use) != len(frame_numbers):
                raise ValueError(
                    f"Requested {len(frame_numbers)} frame numbers but only found "
                    f"{len(observations_to_use)} matching observations"
                )

            logger.debug(f"Calibrating camera {self.camera_id} with {len(observations_to_use)} selected views...")

        # Build object and image points from selected observations
        object_points_views: list[ObjectPoints3D] = []
        image_points_views: list[ImagePoints2D] = []

        for obs in observations_to_use:
            image_points_views.append(np.squeeze(obs.detected_charuco_corners_image_coordinates))
            object_points_views.append(
                self.all_charuco_corners_in_object_coordinates[
                    np.squeeze(obs.detected_charuco_corner_ids), :
                ]
            )

        if len(object_points_views) < len(self.all_charuco_corner_ids):
            raise ValueError(
                f"Need at least {len(self.all_charuco_corner_ids)} observations, "
                f"have {len(object_points_views)}"
            )

        view_count = len(object_points_views)

        if view_count > 50 and frame_numbers is None:
            logger.warning(
                f"Camera {self.camera_id}: Using {view_count} views without optimization. "
                f"Consider calling select_optimal_frame_numbers() first."
            )

        # Run OpenCV calibration
        (
            camera_calibration_residual,
            camera_matrix_output,
            distortion_coefficients_output,
            rotation_vectors_output,
            translation_vectors_output,
        ) = cv2.calibrateCamera(
            objectPoints=object_points_views,
            imagePoints=image_points_views,
            imageSize=self.image_size,
            cameraMatrix=self.camera_matrix.matrix,
            distCoeffs=self.distortion_coefficients.coefficients,
        )

        if not camera_calibration_residual:
            raise ValueError("Camera calibration failed! Check input data.")

        # Store results
        board_rotation_vectors = [
            RotationVector(
                vector=np.squeeze(rotation_vector),
                reference_frame=f"camera-{self.camera_id}",
            )
            for rotation_vector in rotation_vectors_output
        ]
        board_translation_vectors = [
            TranslationVector(
                vector=np.squeeze(translation_vector),
                reference_frame=f"camera-{self.camera_id}",
            )
            for translation_vector in translation_vectors_output
        ]

        logger.debug(
            f"Camera {self.camera_id} calibration complete! "
            f"Residual: {camera_calibration_residual:.4f}"
        )

        if store_results_in_state:
            self.camera_calibration_residual = camera_calibration_residual
            self.camera_matrix = CameraMatrix(matrix=camera_matrix_output)
            self.distortion_coefficients = CameraDistortionCoefficients(
                coefficients=np.squeeze(distortion_coefficients_output)
            )
            self.board_rotation_vectors = board_rotation_vectors
            self.board_translation_vectors = board_translation_vectors
            self._update_reprojection_error(
                object_points_views=object_points_views,
                image_points_views=image_points_views,
            )
        return camera_calibration_residual, camera_matrix_output, distortion_coefficients_output, board_rotation_vectors, board_translation_vectors

    def get_board_pose(
            self,
            object_points: np.ndarray,
            image_points: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Estimate board pose from object and image points.

        Args:
            object_points: Nx3 array of 3D points
            image_points: Nx2 array of 2D points

        Returns:
            Tuple of (rotation_vector, translation_vector)
        """
        if len(object_points) < 6:
            raise ValueError("Need at least 6 object points to estimate board pose")
        if not self.has_calibration:
            raise ValueError("Must calibrate camera first")
        if len(object_points) != len(image_points):
            raise ValueError("Object and image points must have same length")

        success, rotation_vector, translation_vector = cv2.solvePnP(
            objectPoints=object_points,
            imagePoints=image_points,
            cameraMatrix=self.camera_matrix.matrix,
            distCoeffs=self.distortion_coefficients.coefficients,
        )

        if not success:
            raise ValueError("Failed to estimate board pose")

        return rotation_vector, translation_vector

    def draw_board_axes(
            self,
            image: np.ndarray,
            observation: BaseObservation
    ) -> np.ndarray:
        """
        Draw 3D axes on the board in the image.

        Args:
            image: Image to draw on
            observation: Observation containing board detection

        Returns:
            Image with axes drawn
        """
        if not self.has_calibration:
            raise ValueError("Must calibrate camera first")
        if observation.detected_charuco_corners_image_coordinates.shape[0] < 6:
            return image

        rotation_vector, translation_vector = self.get_board_pose(
            object_points=observation.detected_charuco_corners_in_object_coordinates,
            image_points=observation.detected_charuco_corners_image_coordinates,
        )

        axis_length = 5
        return cv2.drawFrameAxes(
            image,
            self.camera_matrix.matrix,
            self.distortion_coefficients.coefficients,
            rotation_vector,
            translation_vector,
            axis_length,
        )

    def _validate_observation(self, observation: BaseObservation) -> None:
        """Validate observation matches calibrator configuration."""
        if observation.image_size != self.image_size:
            raise ValueError(
                f"Image size mismatch: expected {self.image_size}, got {observation.image_size}"
            )
        if any(
                corner_id not in self.all_charuco_corner_ids
                for corner_id in observation.detected_charuco_corner_ids
        ):
            raise ValueError(
                f"Invalid charuco corner ID detected: {observation.detected_charuco_corner_ids}"
            )

    def _update_reprojection_error(
            self,
            object_points_views: list[ObjectPoints3D],
            image_points_views: list[ImagePoints2D],
    ) -> None:
        """Compute reprojection error for calibrated views."""
        if len(image_points_views) != len(object_points_views):
            raise ValueError("Image and object points must have same length")
        if len(image_points_views) == 0:
            raise ValueError("No image points provided")
        if len(image_points_views) != len(self.board_rotation_vectors):
            raise ValueError(
                f"Number of views ({len(image_points_views)}) must match "
                f"number of rotation vectors ({len(self.board_rotation_vectors)})"
            )

        self.reprojection_error_per_point_by_view = []
        self.reprojection_error_by_view = []

        for view_index in range(len(image_points_views)):
            projected_image_points, jacobian = cv2.projectPoints(
                objectPoints=object_points_views[view_index],
                rvec=self.board_rotation_vectors[view_index].vector,
                tvec=self.board_translation_vectors[view_index].vector,
                cameraMatrix=self.camera_matrix.matrix,
                distCoeffs=self.distortion_coefficients.coefficients,
                aspectRatio=self.image_size[0] / self.image_size[1],
            )

            self.reprojection_error_per_point_by_view.append(
                np.abs(
                    image_points_views[view_index]
                    - np.squeeze(projected_image_points)
                )
            )

            self.reprojection_error_by_view.append(
                float(np.nanmean(self.reprojection_error_per_point_by_view[-1]))
            )

        self.mean_reprojection_error = float(np.nanmean(self.reprojection_error_by_view))

        logger.debug(
            f"Camera {self.camera_id} - Mean reprojection error: {self.mean_reprojection_error:.3f} pixels"
        )
