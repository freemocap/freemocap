import logging

import numpy as np
from pydantic import BaseModel
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pubsub.pubsub_topics import CameraNodeOutputMessage
from freemocap.core.tasks.calibration_task.calibration_helpers.camera_math_models import TransformationMatrix
from freemocap.core.tasks.calibration_task.calibration_helpers.single_camera_calibrator import (
    CameraIntrinsicsEstimate,
    SingleCameraCalibrator
)
from freemocap.core.tasks.calibration_task.pyceres_bundle_adjuster import PyCeresBundleAdjuster, BundleAdjustmentConfig
from freemocap.core.tasks.calibration_task.shared_view_accumulator import MultiCameraNodeOutputAccumulator, \
    CameraPair

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
    pyceres_bundle_adjuster: PyCeresBundleAdjuster | None = None
    minimum_views_to_reconstruct: int | None = 300

    @classmethod
    def from_camera_ids(cls, camera_ids: list[CameraIdString], principal_camera_id: CameraIdString | None = None):
        return cls(principal_camera_id=principal_camera_id if principal_camera_id is not None else min(camera_ids),
                   camera_id_to_index={camera_id: index for index, camera_id in enumerate(camera_ids)},
                   multi_cam_output_accumulator=MultiCameraNodeOutputAccumulator.create(camera_ids=camera_ids),

                   )

    @property
    def has_calibration(self) -> bool:
        if self.single_camera_calibrators is None or self.multi_camera_calibration_estimate is None:
            return False
        return all(single_camera_calibrator.has_calibration for single_camera_calibrator in
                   self.single_camera_calibrators.values()) and self.multi_camera_calibration_estimate is not None

    @property
    def camera_intrinsics(self) -> dict[CameraIdString, CameraIntrinsicsEstimate]:
        return {camera_id: single_camera_calibrator.camera_intrinsics_estimate for camera_id, single_camera_calibrator
                in
                self.single_camera_calibrators.items()}

    @property
    def ready_to_calibrate(self) -> bool:
        if not self.single_camera_calibrators:
            return False
        return self.all_cameras_have_min_shared_views()

    def receive_camera_node_output(self, multi_frame_number: int,
                                   camera_node_output_by_camera: dict[CameraIdString, CameraNodeOutputMessage]):

        # log multi-camera output
        self.multi_cam_output_accumulator.receive_camera_node_output(multi_frame_number=multi_frame_number,
                                                                     camera_node_output_by_camera=camera_node_output_by_camera)

        # Add views to single camera calibrators
        if self.single_camera_calibrators is None:
            self.initialize_single_camera_calibrators(camera_node_output_by_camera)
        for camera_id, calibrator in self.single_camera_calibrators.items():
            obs = camera_node_output_by_camera[camera_id].charuco_observation
            if obs and obs.charuco_board_visible:
                calibrator.add_observation(obs)

    def initialize_single_camera_calibrators(self, camera_node_output_by_camera: dict[
        CameraIdString, CameraNodeOutputMessage]):

        self.single_camera_calibrators: dict[CameraIdString, SingleCameraCalibrator] = {}
        for camera_id, node_output in camera_node_output_by_camera.items():
            self.single_camera_calibrators[camera_id] = SingleCameraCalibrator.create_initial(
                camera_id=camera_id,
                image_size=node_output.charuco_observation.image_size,
                all_aruco_marker_ids=node_output.charuco_observation.all_aruco_ids,
                all_aruco_corners_in_object_coordinates=node_output.charuco_observation.all_aruco_corners_in_object_coordinates,
                all_charuco_corner_ids=node_output.charuco_observation.all_charuco_ids,
                all_charuco_corners_in_object_coordinates=node_output.charuco_observation.all_charuco_corners_in_object_coordinates
            )

    def all_cameras_have_min_shared_views(self) -> bool:
        return self.multi_cam_output_accumulator.all_cameras_have_min_shared_views(
            min_shared_views=self.minimum_views_to_reconstruct)

    def calibrate(self) -> MultiCameraCalibrationEstimate:
        """
        Calibrate multi-camera system using direct stereo pair analysis.
        Returns initial estimate suitable for triangulation.
        """
        logger.debug(
            f"Calibrating multi-camera system for cameras: {self.single_camera_calibrators.keys()}"
            f" with principal camera: {self.principal_camera_id} and "
            f"{self.multi_cam_output_accumulator.get_shared_view_count_per_camera()} shared views")

        for calibrator in self.single_camera_calibrators.values():
            logger.info(f"Calibrating single camera: {calibrator.camera_id}...")
            calibrator.calibrate()

        return self._create_initial_multi_camera_estimate()

    def _create_initial_multi_camera_estimate(self) -> MultiCameraCalibrationEstimate:
        """Create initial multi-camera calibration estimate from stereo pair analysis."""
        camera_pair_transforms = self._calculate_camera_pair_transforms()
        camera_transforms = self._calculate_camera_to_principal_camera_transforms(camera_pair_transforms)

        self.multi_camera_calibration_estimate = MultiCameraCalibrationEstimate(
            principal_camera_id=self.principal_camera_id,
            camera_transforms_by_camera_id=camera_transforms
        )

        logger.info(
            f"Initial multi-camera calibration complete. "
            f"Use run_bundle_adjustment() for optional refinement."
        )

        return self.multi_camera_calibration_estimate

    def run_bundle_adjustment(
            self,
            config: BundleAdjustmentConfig | None = None
    ) -> MultiCameraCalibrationEstimate:
        """
        Refine calibration using PyCeres bundle adjustment.

        Must call calibrate() first to get initial estimate.

        Args:
            config: Optional bundle adjustment configuration

        Returns:
            Refined multi-camera calibration estimate

        Raises:
            ValueError: If calibrate() has not been called yet
        """
        if self.multi_camera_calibration_estimate is None:
            raise ValueError("Must run calibrate() first before bundle adjustment")

        if self.single_camera_calibrators is None:
            raise ValueError("No single camera calibrators available")

        logger.info("Running PyCeres bundle adjustment optimization...")

        # Set up default config if not provided
        if config is None:
            config = BundleAdjustmentConfig(
                optimize_intrinsics=False,  # Keep intrinsics fixed
                fix_principal_camera=True,  # Fix principal camera at origin
                max_iterations=100,
                use_robust_loss=True,
                robust_loss_scale=1.0,
                num_threads=4
            )

        # Get camera intrinsics
        camera_intrinsics = {}
        for camera_id, calibrator in self.single_camera_calibrators.items():
            camera_intrinsics[camera_id] = (
                calibrator.camera_matrix,
                calibrator.distortion_coefficients
            )

        # Get charuco corners in world coordinates
        first_calibrator = next(iter(self.single_camera_calibrators.values()))
        charuco_corners_3d = first_calibrator.all_charuco_corners_in_object_coordinates

        # Create bundle adjuster
        self.pyceres_bundle_adjuster = PyCeresBundleAdjuster.create(
            principal_camera_id=self.principal_camera_id,
            camera_transforms=self.multi_camera_calibration_estimate.camera_transforms_by_camera_id,
            camera_intrinsics=camera_intrinsics,
            charuco_corners_3d=charuco_corners_3d,
            config=config
        )

        # Get multi-camera views
        multi_camera_views = self.multi_cam_output_accumulator.multi_camera_target_views

        # Compute initial statistics
        logger.info("Initial reprojection errors:")
        initial_stats = self.pyceres_bundle_adjuster.compute_reprojection_statistics(
            multi_camera_views
        )
        for key, value in initial_stats.items():
            if key == "count":
                logger.info(f"  {key}: {value}")
            else:
                logger.info(f"  {key}: {value:.4f} pixels")

        # Run optimization
        optimized_transforms = self.pyceres_bundle_adjuster.optimize(multi_camera_views)

        # Compute final statistics
        logger.info("Final reprojection errors:")
        final_stats = self.pyceres_bundle_adjuster.compute_reprojection_statistics(
            multi_camera_views
        )
        for key, value in final_stats.items():
            if key == "count":
                logger.info(f"  {key}: {value}")
            else:
                logger.info(f"  {key}: {value:.4f} pixels")

        # Update estimate
        self.multi_camera_calibration_estimate = MultiCameraCalibrationEstimate(
            principal_camera_id=self.principal_camera_id,
            camera_transforms_by_camera_id=optimized_transforms
        )

        improvement_pct = (
                (initial_stats["mean"] - final_stats["mean"]) / initial_stats["mean"] * 100
        )
        logger.success(
            f"Bundle adjustment improved mean reprojection error by {improvement_pct:.1f}%"
        )

        return self.multi_camera_calibration_estimate

    def _calculate_camera_to_principal_camera_transforms(self, camera_pair_secondary_camera_transform_estimates: dict[
        CameraPair, TransformationMatrix]) -> dict[CameraIdString, TransformationMatrix]:
        transform_to_principal_camera_by_camera = {self.principal_camera_id: TransformationMatrix(matrix=np.eye(4),
                                                                                                  reference_frame=f"camera {self.principal_camera_id}")}
        transform_to_principal_camera_by_camera.update(
            {camera_id: None for camera_id in self.single_camera_calibrators.keys() if camera_id != self.principal_camera_id})
        # Use the camera pairs to determine other camera transforms relative to the principal camera
        while any([transform is None for transform in transform_to_principal_camera_by_camera.values()]):
            logger.debug(
                f"Calculating camera transforms for cameras: {[camera_id for camera_id, transform in transform_to_principal_camera_by_camera.items() if transform is None]}")
            for camera_pair, transform in camera_pair_secondary_camera_transform_estimates.items():
                if transform_to_principal_camera_by_camera[camera_pair.other_camera_id] is not None:
                    continue
                if camera_pair.base_camera_id == self.principal_camera_id:
                    # Directly use the transform if base is principal camera
                    transform_to_principal_camera_by_camera[camera_pair.other_camera_id] = transform
                elif camera_pair.other_camera_id == self.principal_camera_id:
                    # Transform is inverse if other is principal camera
                    transform_to_principal_camera_by_camera[camera_pair.base_camera_id] = transform.get_inverse()
                else:
                    # If neither camera in the pair is the principal camera, we need to transform the other camera's transform
                    if camera_pair.base_camera_id in transform_to_principal_camera_by_camera:
                        base_to_principal = transform_to_principal_camera_by_camera[camera_pair.base_camera_id]
                        transform_to_principal_camera_by_camera[
                            camera_pair.other_camera_id] = base_to_principal @ transform
                    elif camera_pair.other_camera_id in transform_to_principal_camera_by_camera:
                        other_to_principal = transform_to_principal_camera_by_camera[camera_pair.other_camera_id]
                        transform_to_principal_camera_by_camera[
                            camera_pair.base_camera_id] = other_to_principal @ transform.get_inverse()
        logger.debug(
            f"Camera ID to principal camera transform estimates: {transform_to_principal_camera_by_camera}")
        return transform_to_principal_camera_by_camera

    def _calculate_camera_pair_transforms(self):
        camera_pair_secondary_camera_transform_estimates = {}
        for camera_pair in self.multi_cam_output_accumulator.camera_shared_views.items():
            base_camera_id = camera_pair.base_camera_id
            other_camera_id = camera_pair.other_camera_id

            charuco_transforms_in_base_camera_coordinates = self.single_camera_calibrators[
                base_camera_id].charuco_transformation_matrices
            charuco_transforms_in_other_camera_coordinates = self.single_camera_calibrators[
                other_camera_id].charuco_transformation_matrices

            other_camera_to_base_camera_transforms = []
            for base_camera_transform, other_camera_transform in zip(charuco_transforms_in_base_camera_coordinates,
                                                                     charuco_transforms_in_other_camera_coordinates):
                base_camera_to_board_transform = base_camera_transform.get_inverse()
                other_camera_to_base_camera_transforms.append(base_camera_to_board_transform @ other_camera_transform)

            mean_transform = TransformationMatrix.mean_from_transformation_matrices(
                other_camera_to_base_camera_transforms)
            camera_pair_secondary_camera_transform_estimates[camera_pair] = mean_transform
        return camera_pair_secondary_camera_transform_estimates


if __name__ == "__main__":
    import pickle
    from pathlib import Path

    pickle_path = r"C:\Users\jonma\github_repos\freemocap_organization\freemocap\freemocap\saved_mc_calib.pkl"
    if not Path(pickle_path).exists():
        raise FileNotFoundError(f"File not found: {pickle_path}")
    loaded: MultiCameraCalibrator = pickle.load(open(pickle_path, "rb"))

    # Now you can choose: use initial estimate or run bundle adjustment
    initial_estimate = loaded.calibrate()
    refined_estimate = loaded.run_bundle_adjustment()
    # ## use snippet below to save out state in debug console to re-run w/o camera streams
    # import pickle
    # from pathlib import Path
    #
    # with open(pickle_path, "wb") as f:
    #     pickle.dump(self, f)
