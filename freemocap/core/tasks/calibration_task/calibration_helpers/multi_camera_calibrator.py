import logging

import cv2
import numpy as np
from pydantic import BaseModel
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pubsub.pubsub_topics import CameraNodeOutputMessage
from freemocap.core.tasks.calibration_task.calibration_helpers.camera_math_models import (
    TransformationMatrix,
    RotationVector,
    TranslationVector,
)
from freemocap.core.tasks.calibration_task.calibration_helpers.single_camera_calibrator import (
    CameraIntrinsicsEstimate,
    SingleCameraCalibrator,
)
from freemocap.core.tasks.calibration_task.pyceres_bundle_adjuster import PyCeresBundleAdjuster
from freemocap.core.tasks.calibration_task.scipy_bundle_adjuster import ScipyBundleAdjuster
from freemocap.core.tasks.calibration_task.shared_view_accumulator import (
    MultiCameraNodeOutputAccumulator,
    CameraPair,
)

logger = logging.getLogger(__name__)


class MultiCameraCalibrationEstimate(BaseModel):
    principal_camera_id: CameraIdString
    camera_transforms_by_camera_id: dict[CameraIdString, TransformationMatrix]


class MultiCameraCalibrator(BaseModel):
    principal_camera_id: CameraIdString
    camera_id_to_index: dict[CameraIdString, int]
    multi_cam_output_accumulator: MultiCameraNodeOutputAccumulator

    single_camera_calibrators: dict[CameraIdString, SingleCameraCalibrator] | None = None
    multi_camera_calibration_estimate: MultiCameraCalibrationEstimate | None = None
    bundle_adjuster: ScipyBundleAdjuster | PyCeresBundleAdjuster | None = None
    minimum_views_to_reconstruct: int | None = 100

    @classmethod
    def from_camera_ids(
            cls,
            camera_ids: list[CameraIdString],
            principal_camera_id: CameraIdString | None = None,
    ) -> "MultiCameraCalibrator":
        return cls(
            principal_camera_id=principal_camera_id if principal_camera_id is not None else min(camera_ids),
            camera_id_to_index={camera_id: index for index, camera_id in enumerate(camera_ids)},
            multi_cam_output_accumulator=MultiCameraNodeOutputAccumulator.create(camera_ids=camera_ids),
        )

    @property
    def has_calibration(self) -> bool:
        if self.single_camera_calibrators is None or self.multi_camera_calibration_estimate is None:
            return False
        return all(
            single_camera_calibrator.has_calibration
            for single_camera_calibrator in self.single_camera_calibrators.values()
        ) and self.multi_camera_calibration_estimate is not None

    @property
    def camera_intrinsics(self) -> dict[CameraIdString, CameraIntrinsicsEstimate]:
        if self.single_camera_calibrators is None:
            raise ValueError("Single camera calibrators not initialized")
        return {
            camera_id: single_camera_calibrator.camera_intrinsics_estimate
            for camera_id, single_camera_calibrator in self.single_camera_calibrators.items()
        }

    @property
    def ready_to_calibrate(self) -> bool:
        if not self.single_camera_calibrators:
            return False
        return self.all_cameras_have_min_shared_views()

    def receive_camera_node_output(
            self,
            multi_frame_number: int,
            camera_node_output_by_camera: dict[CameraIdString, CameraNodeOutputMessage],
    ) -> None:
        # Log multi-camera output
        self.multi_cam_output_accumulator.receive_camera_node_output(
            multi_frame_number=multi_frame_number,
            camera_node_output_by_camera=camera_node_output_by_camera,
        )

        # Add views to single camera calibrators
        if self.single_camera_calibrators is None:
            self.initialize_single_camera_calibrators(camera_node_output_by_camera=camera_node_output_by_camera)

        for camera_id, calibrator in self.single_camera_calibrators.items():
            obs = camera_node_output_by_camera[camera_id].charuco_observation
            if obs and obs.charuco_board_visible:
                calibrator.add_observation(observation=obs)

    def initialize_single_camera_calibrators(
            self,
            camera_node_output_by_camera: dict[CameraIdString, CameraNodeOutputMessage],
    ) -> None:
        logger.info(f"Initializing single camera calibrators for {len(camera_node_output_by_camera)} cameras")
        self.single_camera_calibrators = {}

        for camera_id, node_output in camera_node_output_by_camera.items():
            logger.debug(f"Creating calibrator for camera {camera_id}")
            self.single_camera_calibrators[camera_id] = SingleCameraCalibrator.create_initial(
                camera_id=camera_id,
                image_size=node_output.charuco_observation.image_size,
                all_aruco_marker_ids=node_output.charuco_observation.all_aruco_ids,
                all_aruco_corners_in_object_coordinates=node_output.charuco_observation.all_aruco_corners_in_object_coordinates,
                all_charuco_corner_ids=node_output.charuco_observation.all_charuco_ids,
                all_charuco_corners_in_object_coordinates=node_output.charuco_observation.all_charuco_corners_in_object_coordinates,
            )

    def all_cameras_have_min_shared_views(self) -> bool:
        if self.minimum_views_to_reconstruct is None:
            raise ValueError("minimum_views_to_reconstruct is not set")
        return self.multi_cam_output_accumulator.all_cameras_have_min_shared_views(
            min_shared_views=self.minimum_views_to_reconstruct
        )

    def calibrate(self) -> MultiCameraCalibrationEstimate:
        """Calibrate multi-camera system using OpenCV's stereoCalibrate."""
        if self.single_camera_calibrators is None:
            raise ValueError("Single camera calibrators not initialized")

        logger.info(f"Starting multi-camera calibration for cameras: {list(self.single_camera_calibrators.keys())}")
        logger.info(f"Principal camera: {self.principal_camera_id}")
        shared_view_counts = self.multi_cam_output_accumulator.get_shared_view_count_per_camera()
        logger.info(f"Shared view counts: {shared_view_counts}")

        # Step 1: Calibrate each camera individually
        logger.info("=" * 80)
        logger.info("STEP 1: Individual camera calibration")
        logger.info("=" * 80)
        for calibrator in self.single_camera_calibrators.values():
            logger.info(f"Calibrating camera {calibrator.camera_id}...")
            calibrator.calibrate()
            logger.info(
                f"Camera {calibrator.camera_id} calibration complete: "
                f"reprojection error = {calibrator.mean_reprojection_error:.3f} pixels"
            )

        # Step 2: Compute stereo calibration for each camera pair
        logger.info("=" * 80)
        logger.info("STEP 2: Stereo calibration for camera pairs")
        logger.info("=" * 80)
        camera_pair_transforms = self._calculate_camera_pair_transforms_with_stereo_calibrate()

        # Step 3: Build transforms to principal camera
        logger.info("=" * 80)
        logger.info("STEP 3: Computing transforms to principal camera")
        logger.info("=" * 80)
        camera_transforms = self._calculate_camera_to_principal_camera_transforms(
            camera_pair_secondary_camera_transform_estimates=camera_pair_transforms
        )

        self.multi_camera_calibration_estimate = MultiCameraCalibrationEstimate(
            principal_camera_id=self.principal_camera_id,
            camera_transforms_by_camera_id=camera_transforms,
        )

        logger.success(
            "Initial multi-camera calibration complete. "
            "Use run_bundle_adjustment() for optional refinement."
        )

        return self.multi_camera_calibration_estimate

    def run_bundle_adjustment(self) -> MultiCameraCalibrationEstimate:
        """Refine calibration using scipy bundle adjustment."""
        if self.multi_camera_calibration_estimate is None:
            raise ValueError("Must run calibrate() first before bundle adjustment")

        if self.single_camera_calibrators is None:
            raise ValueError("No single camera calibrators available")

        logger.info("=" * 80)
        logger.info("BUNDLE ADJUSTMENT REFINEMENT")
        logger.info("=" * 80)

        # Get camera intrinsics
        camera_intrinsics = {}
        for camera_id, calibrator in self.single_camera_calibrators.items():
            camera_intrinsics[camera_id] = (
                calibrator.camera_matrix,
                calibrator.distortion_coefficients,
            )
            logger.debug(
                f"Camera {camera_id} intrinsics: "
                f"fx={calibrator.camera_matrix.focal_length_x:.2f}, "
                f"fy={calibrator.camera_matrix.focal_length_y:.2f}"
            )

        # Get charuco corners in world coordinates
        first_calibrator = next(iter(self.single_camera_calibrators.values()))
        charuco_corners_3d = first_calibrator.all_charuco_corners_in_object_coordinates
        logger.info(f"Using {len(charuco_corners_3d)} charuco corners as 3D reference points")

        # Create bundle adjuster
        logger.info("Creating scipy bundle adjuster...")
        self.bundle_adjuster = ScipyBundleAdjuster.create(
            principal_camera_id=self.principal_camera_id,
            camera_transforms=self.multi_camera_calibration_estimate.camera_transforms_by_camera_id,
            camera_intrinsics=camera_intrinsics,
            charuco_corners_3d=charuco_corners_3d,
        )

        # Get multi-camera views
        multi_camera_views = self.multi_cam_output_accumulator.multi_camera_views_by_frame
        logger.info(f"Running optimization on {len(multi_camera_views)} multi-camera views...")

        # Run optimization
        optimized_transforms = self.bundle_adjuster.optimize(multi_camera_views=multi_camera_views)

        # Update estimate
        self.multi_camera_calibration_estimate = MultiCameraCalibrationEstimate(
            principal_camera_id=self.principal_camera_id,
            camera_transforms_by_camera_id=optimized_transforms,
        )

        logger.success("Bundle adjustment complete!")
        return self.multi_camera_calibration_estimate

    def _calculate_camera_pair_transforms_with_stereo_calibrate(
            self,
    ) -> dict[CameraPair, TransformationMatrix]:
        """Calculate camera pair transforms using OpenCV's stereoCalibrate."""
        if self.single_camera_calibrators is None:
            raise ValueError("Single camera calibrators not initialized")

        camera_pair_transforms = {}

        for base_camera_id, shared_views_dict in self.multi_cam_output_accumulator.camera_shared_views.items():
            for camera_pair, shared_views in shared_views_dict.items():
                if camera_pair in camera_pair_transforms:
                    logger.debug(f"Skipping already-calculated pair: {camera_pair}")
                    continue

                base_camera_id = camera_pair.base_camera_id
                other_camera_id = camera_pair.other_camera_id

                logger.info(f"Computing stereo calibration: {base_camera_id} ↔ {other_camera_id}")
                logger.debug(f"  Using {len(shared_views)} shared views")

                # Extract matched observations
                object_points_list = []
                base_image_points_list = []
                other_image_points_list = []

                for view in shared_views:
                    base_obs = view.base_camera_observation
                    other_obs = view.other_camera_observation

                    # Find common corner IDs between the two observations
                    base_corner_ids = set(base_obs.detected_charuco_corner_ids)
                    other_corner_ids = set(other_obs.detected_charuco_corner_ids)
                    common_corner_ids = base_corner_ids & other_corner_ids

                    if len(common_corner_ids) < 6:
                        logger.debug(
                            f"  Skipping frame {view.multi_frame_number}: "
                            f"only {len(common_corner_ids)} common corners"
                        )
                        continue

                    # Build matched point arrays
                    common_corner_ids_sorted = sorted(common_corner_ids)

                    object_points = []
                    base_image_points = []
                    other_image_points = []

                    for corner_id in common_corner_ids_sorted:
                        # Get 3D object point
                        object_points.append(
                            self.single_camera_calibrators[base_camera_id]
                            .all_charuco_corners_in_object_coordinates[corner_id]
                        )

                        # Get 2D image points
                        base_idx = np.where(base_obs.detected_charuco_corner_ids == corner_id)[0][0]
                        other_idx = np.where(other_obs.detected_charuco_corner_ids == corner_id)[0][0]

                        base_image_points.append(base_obs.detected_charuco_corners_image_coordinates[base_idx])
                        other_image_points.append(other_obs.detected_charuco_corners_image_coordinates[other_idx])

                    object_points_list.append(np.array(object_points, dtype=np.float32))
                    base_image_points_list.append(np.array(base_image_points, dtype=np.float32))
                    other_image_points_list.append(np.array(other_image_points, dtype=np.float32))

                if len(object_points_list) < 10:
                    raise ValueError(
                        f"Insufficient matched views for stereo calibration between "
                        f"{base_camera_id} and {other_camera_id}: only {len(object_points_list)} views"
                    )

                logger.info(f"  Using {len(object_points_list)} matched views for stereo calibration")

                # Get intrinsics
                base_calibrator = self.single_camera_calibrators[base_camera_id]
                other_calibrator = self.single_camera_calibrators[other_camera_id]

                # Run stereoCalibrate
                logger.debug("  Running cv2.stereoCalibrate...")
                (
                    rms_error,
                    camera_matrix_1,
                    dist_coeffs_1,
                    camera_matrix_2,
                    dist_coeffs_2,
                    R,
                    T,
                    E,
                    F,
                ) = cv2.stereoCalibrate(
                    objectPoints=object_points_list,
                    imagePoints1=base_image_points_list,
                    imagePoints2=other_image_points_list,
                    cameraMatrix1=base_calibrator.camera_matrix.matrix.copy(),
                    distCoeffs1=base_calibrator.distortion_coefficients.coefficients.copy(),
                    cameraMatrix2=other_calibrator.camera_matrix.matrix.copy(),
                    distCoeffs2=other_calibrator.distortion_coefficients.coefficients.copy(),
                    imageSize=base_calibrator.image_size,
                    flags=cv2.CALIB_FIX_INTRINSIC,  # Don't re-optimize intrinsics
                    criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-6),
                )

                logger.info(f"  Stereo calibration RMS error: {rms_error:.4f} pixels")
                logger.debug(f"  Rotation matrix norm: {np.linalg.norm(R):.4f}")
                logger.debug(f"  Translation vector norm: {np.linalg.norm(T):.4f}")

                # Convert R, T to TransformationMatrix (other_camera -> base_camera)
                rotation_vector = RotationVector(
                    vector=np.squeeze(cv2.Rodrigues(R)[0]),
                    reference_frame=f"camera-{base_camera_id}",
                )
                translation_vector = TranslationVector(
                    vector=np.squeeze(T),
                    reference_frame=f"camera-{base_camera_id}",
                )

                transform = TransformationMatrix.from_rotation_translation(
                    rotation_vector=rotation_vector,
                    translation_vector=translation_vector,
                )

                camera_pair_transforms[camera_pair] = transform
                logger.debug(f"  Transform computed successfully")

        logger.info(f"Computed {len(camera_pair_transforms)} stereo calibrations")
        return camera_pair_transforms

    def _calculate_camera_to_principal_camera_transforms(
            self,
            camera_pair_secondary_camera_transform_estimates: dict[CameraPair, TransformationMatrix],
    ) -> dict[CameraIdString, TransformationMatrix]:
        """Build transforms from all cameras to principal camera using pairwise transforms."""
        if self.single_camera_calibrators is None:
            raise ValueError("Single camera calibrators not initialized")

        # Start with principal camera at identity
        transform_to_principal_camera_by_camera = {
            self.principal_camera_id: TransformationMatrix(
                matrix=np.eye(4, dtype=np.float64),
                reference_frame=f"camera-{self.principal_camera_id}",
            )
        }

        # Initialize other cameras as None
        for camera_id in self.single_camera_calibrators.keys():
            if camera_id != self.principal_camera_id:
                transform_to_principal_camera_by_camera[camera_id] = None

        logger.info(f"Building transform graph from principal camera: {self.principal_camera_id}")

        # Iteratively resolve transforms using available pairs
        iteration = 0
        while any(transform is None for transform in transform_to_principal_camera_by_camera.values()):
            iteration += 1
            unresolved = [
                camera_id
                for camera_id, transform in transform_to_principal_camera_by_camera.items()
                if transform is None
            ]
            logger.debug(f"Iteration {iteration}: {len(unresolved)} unresolved cameras: {unresolved}")

            progress_made = False

            for camera_pair, pair_transform in camera_pair_secondary_camera_transform_estimates.items():
                base_id = camera_pair.base_camera_id
                other_id = camera_pair.other_camera_id

                # Skip if other camera already resolved
                if transform_to_principal_camera_by_camera[other_id] is not None:
                    continue

                # Case 1: base is principal camera
                if base_id == self.principal_camera_id:
                    logger.debug(f"  Resolved {other_id} directly from principal camera")
                    transform_to_principal_camera_by_camera[other_id] = pair_transform
                    progress_made = True

                # Case 2: other is principal camera
                elif other_id == self.principal_camera_id:
                    logger.debug(f"  Resolved {base_id} as inverse from principal camera")
                    transform_to_principal_camera_by_camera[base_id] = pair_transform.get_inverse()
                    progress_made = True

                # Case 3: base is resolved, other is not
                elif transform_to_principal_camera_by_camera[base_id] is not None:
                    base_to_principal = transform_to_principal_camera_by_camera[base_id]
                    logger.debug(f"  Resolved {other_id} via {base_id}")
                    transform_to_principal_camera_by_camera[other_id] = base_to_principal @ pair_transform
                    progress_made = True

                # Case 4: other is resolved, base is not
                elif transform_to_principal_camera_by_camera[other_id] is not None:
                    other_to_principal = transform_to_principal_camera_by_camera[other_id]
                    logger.debug(f"  Resolved {base_id} via {other_id} (inverse)")
                    transform_to_principal_camera_by_camera[base_id] = (
                            other_to_principal @ pair_transform.get_inverse()
                    )
                    progress_made = True

            if not progress_made:
                unresolved_cameras = [
                    cid for cid, t in transform_to_principal_camera_by_camera.items() if t is None
                ]
                raise RuntimeError(
                    f"Cannot resolve transforms for cameras {unresolved_cameras}. "
                    f"Camera network may not be fully connected to principal camera."
                )

        logger.success(f"All camera transforms resolved in {iteration} iterations")

        # Log final transforms
        for camera_id, transform in transform_to_principal_camera_by_camera.items():
            if camera_id == self.principal_camera_id:
                logger.info(f"  Camera {camera_id}: [Principal camera - identity]")
            else:
                t = transform.translation_vector.vector
                logger.info(
                    f"  Camera {camera_id}: translation=[{t[0]:.3f}, {t[1]:.3f}, {t[2]:.3f}]"
                )

        return transform_to_principal_camera_by_camera


if __name__ == "__main__":
    import pickle
    from pathlib import Path

    pickle_path = r"C:\Users\jonma\github_repos\freemocap_organization\freemocap\freemocap\saved_mc_calib.pkl"
    if not Path(pickle_path).exists():
        raise FileNotFoundError(f"File not found: {pickle_path}")

    logger.info(f"Loading calibrator from: {pickle_path}")
    loaded: MultiCameraCalibrator = pickle.load(open(pickle_path, "rb"))

    # Run calibration
    logger.info("Starting calibration process...")
    loaded.calibrate()

    logger.info("Running bundle adjustment refinement...")
    refined_estimate = loaded.run_bundle_adjustment()

    logger.success("Calibration pipeline complete!")