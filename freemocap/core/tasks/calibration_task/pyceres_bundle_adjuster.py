import logging
from dataclasses import dataclass

import numpy as np
import pyceres
import cv2
from pydantic import BaseModel, Field
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.tasks.calibration_task.calibration_helpers.camera_math_models import (
    CameraMatrix,
    CameraDistortionCoefficients,
    TransformationMatrix,
)
from freemocap.core.tasks.calibration_task.shared_view_accumulator import MultiCameraTargetView

logger = logging.getLogger(__name__)


class ReprojectionCost(pyceres.CostFunction):
    """
    Cost function for bundle adjustment that computes reprojection error.
    
    Residual = observed_2d - project(transform(point_3d, extrinsics), intrinsics)
    """
    
    def __init__(
        self,
        observed_point: np.ndarray,
        point_3d: np.ndarray,
        fix_intrinsics: bool = True
    ):
        super().__init__()
        if observed_point.shape != (2,):
            raise ValueError(f"observed_point must be shape (2,), got {observed_point.shape}")
        if point_3d.shape != (3,):
            raise ValueError(f"point_3d must be shape (3,), got {point_3d.shape}")
        
        self.observed_point = observed_point.astype(np.float64)
        self.point_3d = point_3d.astype(np.float64)
        self.fix_intrinsics = fix_intrinsics
        
        # Set up parameter blocks:
        # extrinsics (6: rvec[3] + tvec[3])
        # intrinsics (9: fx, fy, cx, cy, k1, k2, p1, p2, k3)
        if fix_intrinsics:
            self.set_num_residuals(2)
            self.set_parameter_block_sizes([6])
        else:
            self.set_num_residuals(2)
            self.set_parameter_block_sizes([6, 9]) # extrinsics + intrinsics
    
    def Evaluate(
        self,
        parameters: list[np.ndarray],
        residuals: np.ndarray,
        jacobians: list[np.ndarray] | None
    ) -> bool:
        """
        Evaluate reprojection error and optionally compute jacobians.
        
        Args:
            parameters: List containing [extrinsics] or [extrinsics, intrinsics]
            residuals: Output array of shape (2,) for x,y reprojection errors
            jacobians: Optional list of jacobian matrices to fill
            
        Returns:
            True if evaluation succeeded
        """
        try:
            extrinsics = parameters[0]
            
            if self.fix_intrinsics:
                # Intrinsics will be passed separately when calling Evaluate
                if len(parameters) != 1:
                    raise ValueError(f"Expected 1 parameter block, got {len(parameters)}")
            else:
                if len(parameters) != 2:
                    raise ValueError(f"Expected 2 parameter blocks, got {len(parameters)}")
                intrinsics = parameters[1]
            
            # Extract rotation and translation
            rvec = extrinsics[0:3].reshape(3, 1)
            tvec = extrinsics[3:6].reshape(3, 1)
            
            # Build camera matrix and distortion from intrinsics
            if self.fix_intrinsics:
                # These will be set from the outer scope
                camera_matrix = self._camera_matrix
                dist_coeffs = self._dist_coeffs
            else:
                fx, fy, cx, cy = intrinsics[0:4]
                camera_matrix = np.array([
                    [fx, 0, cx],
                    [0, fy, cy],
                    [0, 0, 1]
                ], dtype=np.float64)
                dist_coeffs = intrinsics[4:9]
            
            # Project 3D point to 2D
            point_3d = self.point_3d.reshape(1, 3)
            projected, jacobian = cv2.projectPoints(
                objectPoints=point_3d,
                rvec=rvec,
                tvec=tvec,
                cameraMatrix=camera_matrix,
                distCoeffs=dist_coeffs
            )
            
            projected_point = projected.squeeze()
            
            # Compute residual
            residuals[0] = projected_point[0] - self.observed_point[0]
            residuals[1] = projected_point[1] - self.observed_point[1]
            
            # Jacobians are computed numerically by Ceres if not provided
            # For production code, you'd want to compute analytical jacobians here
            
            return True
            
        except Exception as e:
            logger.error(f"Error in ReprojectionCost.Evaluate: {e}")
            return False
    
    def set_intrinsics(
        self,
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray
    ) -> None:
        """Set fixed intrinsics for this cost function."""
        self._camera_matrix = camera_matrix
        self._dist_coeffs = dist_coeffs


@dataclass
class BundleAdjustmentConfig:
    """Configuration for pyceres bundle adjustment."""
    optimize_intrinsics: bool = False
    fix_principal_camera: bool = True
    max_iterations: int = 100
    function_tolerance: float = 1e-6
    gradient_tolerance: float = 1e-10
    parameter_tolerance: float = 1e-8
    use_robust_loss: bool = True
    robust_loss_scale: float = 1.0
    num_threads: int = 4


class CameraParameters(BaseModel):
    """Container for camera parameters during optimization."""
    camera_id: CameraIdString
    extrinsics: np.ndarray = Field(default_factory=lambda: np.zeros(6, dtype=np.float64))
    intrinsics: np.ndarray = Field(default_factory=lambda: np.zeros(9, dtype=np.float64))
    
    class Config:
        arbitrary_types_allowed = True
    
    @classmethod
    def from_calibration_data(
        cls,
        camera_id: CameraIdString,
        rotation_vector: np.ndarray,
        translation_vector: np.ndarray,
        camera_matrix: CameraMatrix,
        distortion_coeffs: CameraDistortionCoefficients
    ) -> "CameraParameters":
        """Create from existing calibration data."""
        if rotation_vector.shape != (3,):
            raise ValueError(f"rotation_vector must be shape (3,), got {rotation_vector.shape}")
        if translation_vector.shape != (3,):
            raise ValueError(f"translation_vector must be shape (3,), got {translation_vector.shape}")
        
        extrinsics = np.zeros(6, dtype=np.float64)
        extrinsics[0:3] = rotation_vector
        extrinsics[3:6] = translation_vector
        
        intrinsics = np.zeros(9, dtype=np.float64)
        intrinsics[0] = camera_matrix.focal_length_x
        intrinsics[1] = camera_matrix.focal_length_y
        intrinsics[2], intrinsics[3] = camera_matrix.principal_point
        
        # Handle variable length distortion coefficients
        dist = distortion_coeffs.coefficients
        num_dist = min(len(dist), 5)
        intrinsics[4:4+num_dist] = dist[0:num_dist]
        
        return cls(
            camera_id=camera_id,
            extrinsics=extrinsics,
            intrinsics=intrinsics
        )
    
    def to_transformation_matrix(self, reference_frame: str) -> TransformationMatrix:
        """Convert extrinsics to TransformationMatrix."""
        rotation_matrix = cv2.Rodrigues(self.extrinsics[0:3])[0]
        translation = self.extrinsics[3:6]
        
        matrix = np.eye(4, dtype=np.float64)
        matrix[0:3, 0:3] = rotation_matrix
        matrix[0:3, 3] = translation
        
        return TransformationMatrix(
            matrix=matrix,
            reference_frame=reference_frame
        )
    
    def to_camera_matrix(self) -> CameraMatrix:
        """Convert intrinsics to CameraMatrix."""
        matrix = np.eye(3, dtype=np.float64)
        matrix[0, 0] = self.intrinsics[0]  # fx
        matrix[1, 1] = self.intrinsics[1]  # fy
        matrix[0, 2] = self.intrinsics[2]  # cx
        matrix[1, 2] = self.intrinsics[3]  # cy
        return CameraMatrix(matrix=matrix)
    
    def to_distortion_coefficients(self) -> CameraDistortionCoefficients:
        """Convert intrinsics to CameraDistortionCoefficients."""
        return CameraDistortionCoefficients(
            coefficients=self.intrinsics[4:9]
        )


class PyCeresBundleAdjuster(BaseModel):
    """
    pyceres-based bundle adjuster for multi-camera calibration.
    
    Optimizes camera extrinsics (and optionally intrinsics) to minimize
    reprojection errors across all cameras and observations.
    """
    
    config: BundleAdjustmentConfig
    principal_camera_id: CameraIdString
    camera_parameters: dict[CameraIdString, CameraParameters] = Field(default_factory=dict)
    point_3d_coords: dict[int, np.ndarray] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True
    
    @classmethod
    def create(
        cls,
        principal_camera_id: CameraIdString,
        camera_transforms: dict[CameraIdString, TransformationMatrix],
        camera_intrinsics: dict[CameraIdString, tuple[CameraMatrix, CameraDistortionCoefficients]],
        charuco_corners_3d: np.ndarray,
        config: BundleAdjustmentConfig | None = None
    ):
        """
        Create bundle adjuster from initial calibration estimates.
        
        Args:
            principal_camera_id: ID of the principal/reference camera
            camera_transforms: Initial extrinsic transforms for each camera
            camera_intrinsics: Initial intrinsic parameters for each camera
            charuco_corners_3d: 3D coordinates of all charuco corners in world frame
            config: Optional configuration
        """
        if config is None:
            config = BundleAdjustmentConfig()
        
        camera_parameters: dict[CameraIdString, CameraParameters] = {}
        
        for camera_id in camera_transforms.keys():
            if camera_id not in camera_intrinsics:
                raise ValueError(f"No intrinsics found for camera {camera_id}")
            
            transform = camera_transforms[camera_id]
            camera_matrix, dist_coeffs = camera_intrinsics[camera_id]
            
            # Extract rotation and translation from transform
            rotation_matrix = transform.rotation_matrix
            translation = transform.translation_vector.vector
            rotation_vector = cv2.Rodrigues(rotation_matrix)[0].squeeze()
            
            camera_parameters[camera_id] = CameraParameters.from_calibration_data(
                camera_id=camera_id,
                rotation_vector=rotation_vector,
                translation_vector=translation,
                camera_matrix=camera_matrix,
                distortion_coeffs=dist_coeffs
            )
        
        # Initialize 3D point coordinates
        point_3d_coords = {
            i: charuco_corners_3d[i].astype(np.float64)
            for i in range(len(charuco_corners_3d))
        }
        
        return cls(
            config=config,
            principal_camera_id=principal_camera_id,
            camera_parameters=camera_parameters,
            point_3d_coords=point_3d_coords
        )
    
    def optimize(
        self,
        multi_camera_views: dict[int, MultiCameraTargetView]
    ) -> dict[CameraIdString, TransformationMatrix]:
        """
        Run bundle adjustment optimization.
        
        Args:
            multi_camera_views: Dictionary of multi-camera observations
            
        Returns:
            Optimized camera transforms
        """
        logger.info("Setting up pyceres bundle adjustment problem...")
        
        problem = pyceres.Problem()
        
        # Add parameter blocks for each camera
        for camera_id, params in self.camera_parameters.items():
            problem.AddParameterBlock(params.extrinsics)
            if not self.config.optimize_intrinsics:
                problem.AddParameterBlock(params.intrinsics)
        
        # Fix principal camera at origin if requested
        if self.config.fix_principal_camera:
            principal_params = self.camera_parameters[self.principal_camera_id]
            problem.SetParameterBlockConstant(principal_params.extrinsics)
            logger.info(f"Fixed principal camera {self.principal_camera_id} at origin")
        
        # Add residual blocks for all observations
        residual_count = 0
        
        for frame_number, mc_view in multi_camera_views.items():
            for camera_id, camera_output in mc_view.camera_node_output_by_camera.items():
                if camera_output.charuco_observation is None:
                    continue
                if camera_output.charuco_observation.charuco_empty:
                    continue
                
                obs = camera_output.charuco_observation
                
                # Get camera parameters
                cam_params = self.camera_parameters[camera_id]
                
                # Add residual for each detected charuco corner
                for corner_idx, corner_id in enumerate(obs.detected_charuco_corner_ids):
                    corner_id_int = int(corner_id)
                    
                    if corner_id_int not in self.point_3d_coords:
                        logger.warning(f"Corner ID {corner_id_int} not in 3D coordinates, skipping")
                        continue
                    
                    observed_2d = obs.detected_charuco_corners_image_coordinates[corner_idx]
                    point_3d = self.point_3d_coords[corner_id_int]
                    
                    # Create cost function
                    cost = ReprojectionCost(
                        observed_point=observed_2d,
                        point_3d=point_3d,
                        fix_intrinsics=not self.config.optimize_intrinsics
                    )
                    
                    if not self.config.optimize_intrinsics:
                        # Set fixed intrinsics
                        cost.set_intrinsics(
                            camera_matrix=cam_params.to_camera_matrix().matrix,
                            dist_coeffs=cam_params.to_distortion_coefficients().coefficients
                        )
                        
                        # Add residual with only extrinsics
                        if self.config.use_robust_loss:
                            loss = pyceres.HuberLoss(self.config.robust_loss_scale)
                            problem.AddResidualBlock(
                                cost,
                                loss,
                                [cam_params.extrinsics]
                            )
                        else:
                            problem.AddResidualBlock(
                                cost,
                                None,
                                [cam_params.extrinsics]
                            )
                    else:
                        # Add residual with extrinsics and intrinsics
                        if self.config.use_robust_loss:
                            loss = pyceres.HuberLoss(self.config.robust_loss_scale)
                            problem.AddResidualBlock(
                                cost,
                                loss,
                                [cam_params.extrinsics, cam_params.intrinsics]
                            )
                        else:
                            problem.AddResidualBlock(
                                cost,
                                None,
                                [cam_params.extrinsics, cam_params.intrinsics]
                            )
                    
                    residual_count += 1
        
        logger.info(f"Added {residual_count} residual blocks to optimization problem")
        
        if residual_count == 0:
            raise ValueError("No residuals added to problem - check observations and 3D points")
        
        # Configure solver
        options = pyceres.SolverOptions()
        options.max_num_iterations = self.config.max_iterations
        options.function_tolerance = self.config.function_tolerance
        options.gradient_tolerance = self.config.gradient_tolerance
        options.parameter_tolerance = self.config.parameter_tolerance
        options.num_threads = self.config.num_threads
        options.minimizer_progress_to_stdout = True
        
        logger.info("Running bundle adjustment optimization...")
        summary = pyceres.Summary()
        pyceres.Solve(options, problem, summary)
        
        logger.info(f"Bundle adjustment complete:")
        logger.info(f"  Initial cost: {summary.initial_cost:.6f}")
        logger.info(f"  Final cost: {summary.final_cost:.6f}")
        logger.info(f"  Iterations: {summary.num_successful_steps}")
        logger.info(f"  Termination: {summary.termination_type}")
        
        if not summary.IsSolutionUsable():
            logger.error("Optimization failed to produce usable solution!")
            raise RuntimeError(f"Bundle adjustment failed: {summary.termination_type}")
        
        # Extract optimized transforms
        optimized_transforms: dict[CameraIdString, TransformationMatrix] = {}
        
        for camera_id, params in self.camera_parameters.items():
            transform = params.to_transformation_matrix(
                reference_frame=f"camera-{self.principal_camera_id}"
            )
            optimized_transforms[camera_id] = transform
            
            logger.debug(f"Camera {camera_id} optimized transform:\n{transform}")
        
        return optimized_transforms
    
    def compute_reprojection_statistics(
        self,
        multi_camera_views: dict[int, MultiCameraTargetView]
    ) -> dict[str, float]:
        """
        Compute reprojection error statistics for current parameters.
        
        Returns:
            Dictionary with mean, median, std, min, max reprojection errors
        """
        errors: list[float] = []
        
        for frame_number, mc_view in multi_camera_views.items():
            for camera_id, camera_output in mc_view.camera_node_output_by_camera.items():
                if camera_output.charuco_observation is None:
                    continue
                if camera_output.charuco_observation.charuco_empty:
                    continue
                
                obs = camera_output.charuco_observation
                cam_params = self.camera_parameters[camera_id]
                
                # Get camera calibration
                rvec = cam_params.extrinsics[0:3].reshape(3, 1)
                tvec = cam_params.extrinsics[3:6].reshape(3, 1)
                camera_matrix = cam_params.to_camera_matrix().matrix
                dist_coeffs = cam_params.to_distortion_coefficients().coefficients
                
                # Project 3D points
                for corner_idx, corner_id in enumerate(obs.detected_charuco_corner_ids):
                    corner_id_int = int(corner_id)
                    
                    if corner_id_int not in self.point_3d_coords:
                        continue
                    
                    observed_2d = obs.detected_charuco_corners_image_coordinates[corner_idx]
                    point_3d = self.point_3d_coords[corner_id_int].reshape(1, 3)
                    
                    projected, _ = cv2.projectPoints(
                        objectPoints=point_3d,
                        rvec=rvec,
                        tvec=tvec,
                        cameraMatrix=camera_matrix,
                        distCoeffs=dist_coeffs
                    )
                    
                    projected_2d = projected.squeeze()
                    error = np.linalg.norm(projected_2d - observed_2d)
                    errors.append(error)
        
        if len(errors) == 0:
            raise ValueError("No reprojection errors computed")
        
        errors_array = np.array(errors)
        
        return {
            "mean": float(np.mean(errors_array)),
            "median": float(np.median(errors_array)),
            "std": float(np.std(errors_array)),
            "min": float(np.min(errors_array)),
            "max": float(np.max(errors_array)),
            "count": len(errors)
        }
