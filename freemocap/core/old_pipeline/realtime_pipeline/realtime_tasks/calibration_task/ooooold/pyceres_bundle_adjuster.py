import logging

import cv2
import numpy as np
import pyceres
from pydantic import BaseModel, Field
from scipy.spatial.transform import Rotation
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.calibration_helpers.camera_math_models import (
    CameraMatrix,
    CameraDistortionCoefficients,
    TransformationMatrix,
)
from freemocap.core.pipeline.realtime_pipeline.realtime_tasks.calibration_task.shared_view_accumulator import MultiCameraTargetView

logger = logging.getLogger(__name__)


class ReprojectionCost(pyceres.CostFunction):
    def __init__(
            self,
            observed_point: np.ndarray,
            point_3d: np.ndarray,
            fx: float,
            fy: float,
            cx: float,
            cy: float,
    ) -> None:
        super().__init__()
        self.observed_point = observed_point.astype(np.float64).copy()
        self.point_3d = point_3d.astype(np.float64).copy()
        self.fx = fx
        self.fy = fy
        self.cx = cx
        self.cy = cy

        self.set_num_residuals(2)
        # Separate rvec and tvec like the working code separates quat and trans!
        self.set_parameter_block_sizes([3, 3])

    def Evaluate(
            self,
            parameters: list[np.ndarray],
            residuals: np.ndarray,
            jacobians: list[np.ndarray] | None,
    ) -> bool:
        rvec = parameters[0]
        tvec = parameters[1]

        # Convert rotation vector to rotation matrix
        angle = np.linalg.norm(rvec)
        if angle < 1e-10:
            R = np.eye(3, dtype=np.float64)
        else:
            R = Rotation.from_rotvec(rvec).as_matrix()

        # Transform 3D point to camera coordinates
        X_cam = R @ self.point_3d + tvec

        # Check for points behind camera
        if X_cam[2] < 1e-6:
            residuals[0] = 1000.0
            residuals[1] = 1000.0
            return True

        # Project to normalized image coordinates (no distortion for now)
        x = X_cam[0] / X_cam[2]
        y = X_cam[1] / X_cam[2]

        # Apply camera matrix
        u = self.fx * x + self.cx
        v = self.fy * y + self.cy

        # Compute residuals
        residuals[0] = u - self.observed_point[0]
        residuals[1] = v - self.observed_point[1]

        return True


class CameraParameters(BaseModel):
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
            distortion_coeffs: CameraDistortionCoefficients,
    ) -> "CameraParameters":
        extrinsics = np.zeros(6, dtype=np.float64)
        extrinsics[0:3] = rotation_vector.flatten()
        extrinsics[3:6] = translation_vector.flatten()

        intrinsics = np.zeros(9, dtype=np.float64)
        intrinsics[0] = camera_matrix.focal_length_x
        intrinsics[1] = camera_matrix.focal_length_y
        intrinsics[2], intrinsics[3] = camera_matrix.principal_point

        dist = distortion_coeffs.coefficients if hasattr(distortion_coeffs, "coefficients") else distortion_coeffs
        num_dist = min(len(dist), 5)
        intrinsics[4: 4 + num_dist] = dist[0:num_dist]

        return cls(camera_id=camera_id, extrinsics=extrinsics, intrinsics=intrinsics)

    def to_transformation_matrix(self, reference_frame: str) -> TransformationMatrix:
        rotation_matrix = cv2.Rodrigues(self.extrinsics[0:3])[0]
        matrix = np.eye(4, dtype=np.float64)
        matrix[0:3, 0:3] = rotation_matrix
        matrix[0:3, 3] = self.extrinsics[3:6]
        return TransformationMatrix(matrix=matrix, reference_frame=reference_frame)

    def to_camera_matrix(self) -> np.ndarray:
        matrix = np.eye(3, dtype=np.float64)
        matrix[0, 0] = self.intrinsics[0]
        matrix[1, 1] = self.intrinsics[1]
        matrix[0, 2] = self.intrinsics[2]
        matrix[1, 2] = self.intrinsics[3]
        return matrix

    def to_distortion_coefficients(self) -> np.ndarray:
        return self.intrinsics[4:9]


class PyCeresBundleAdjuster(BaseModel):
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
    ) -> "PyCeresBundleAdjuster":
        camera_parameters = {}
        for camera_id, transform in camera_transforms.items():
            camera_matrix, dist_coeffs = camera_intrinsics[camera_id]
            rotation_vector = cv2.Rodrigues(transform.rotation_matrix)[0].flatten()
            translation = transform.translation_vector.vector.flatten()
            camera_parameters[camera_id] = CameraParameters.from_calibration_data(
                camera_id=camera_id,
                rotation_vector=rotation_vector,
                translation_vector=translation,
                camera_matrix=camera_matrix,
                distortion_coeffs=dist_coeffs,
            )

        point_3d_coords = {i: charuco_corners_3d[i].astype(np.float64).copy() for i in range(len(charuco_corners_3d))}
        return cls(
            principal_camera_id=principal_camera_id,
            camera_parameters=camera_parameters,
            point_3d_coords=point_3d_coords,
        )

    def optimize(
            self,
            multi_camera_views: dict[int, MultiCameraTargetView],
    ) -> dict[CameraIdString, TransformationMatrix]:
        logger.info("Starting PyCeres bundle adjustment optimization (FIXED STRUCTURE)...")

        # FOLLOW THE WORKING CODE'S PATTERN EXACTLY
        # 1. Create separate arrays for rotation and translation (like quat and trans)
        camera_ids = sorted(self.camera_parameters.keys())

        # Store rotation and translation SEPARATELY like the working code
        rvecs: list[np.ndarray] = []
        tvecs: list[np.ndarray] = []
        rvec_by_id: dict[CameraIdString, np.ndarray] = {}
        tvec_by_id: dict[CameraIdString, np.ndarray] = {}

        for camera_id in camera_ids:
            params = self.camera_parameters[camera_id]
            rvec = np.array(params.extrinsics[0:3], dtype=np.float64, order='C')
            tvec = np.array(params.extrinsics[3:6], dtype=np.float64, order='C')
            rvecs.append(rvec)
            tvecs.append(tvec)
            rvec_by_id[camera_id] = rvec
            tvec_by_id[camera_id] = tvec

        # Keep all cost functions alive
        cost_functions: list[ReprojectionCost] = []

        problem = pyceres.Problem()

        # Add parameter blocks separately like the working code
        for camera_id in camera_ids:
            problem.add_parameter_block(rvec_by_id[camera_id], 3)
            problem.add_parameter_block(tvec_by_id[camera_id], 3)

        # Fix the principal camera
        problem.set_parameter_block_constant(rvec_by_id[self.principal_camera_id])
        problem.set_parameter_block_constant(tvec_by_id[self.principal_camera_id])

        # Add residual blocks
        residual_count = 0
        for mc_view in multi_camera_views.values():
            for camera_id, camera_output in mc_view.camera_node_output_by_camera.items():
                if not camera_output.observation or camera_output.observation.charuco_empty:
                    continue

                obs = camera_output.observation
                params = self.camera_parameters[camera_id]
                camera_matrix = params.to_camera_matrix()

                fx = float(camera_matrix[0, 0])
                fy = float(camera_matrix[1, 1])
                cx = float(camera_matrix[0, 2])
                cy = float(camera_matrix[1, 2])

                rvec = rvec_by_id[camera_id]
                tvec = tvec_by_id[camera_id]

                for corner_idx, corner_id in enumerate(obs.detected_charuco_corner_ids):
                    corner_id_int = int(corner_id)
                    if corner_id_int not in self.point_3d_coords:
                        continue

                    cost = ReprojectionCost(
                        observed_point=obs.detected_charuco_corners_image_coordinates[corner_idx],
                        point_3d=self.point_3d_coords[corner_id_int],
                        fx=fx,
                        fy=fy,
                        cx=cx,
                        cy=cy,
                    )
                    cost_functions.append(cost)
                    # Pass BOTH parameter blocks like the working code!
                    problem.add_residual_block(cost, None, [rvec, tvec])
                    residual_count += 1

        logger.info(f"Added {residual_count} reprojection residuals")
        logger.info(f"Total parameter blocks: {problem.num_parameters()}")
        logger.info(f"Total residual blocks: {problem.num_residual_blocks()}")

        # Configure solver - match the working code exactly
        options = pyceres.SolverOptions()
        options.max_num_iterations = 100
        options.minimizer_progress_to_stdout = True
        options.linear_solver_type = pyceres.LinearSolverType.SPARSE_NORMAL_CHOLESKY
        options.function_tolerance = 1e-9  # Match working code
        options.gradient_tolerance = 1e-11  # Match working code
        options.parameter_tolerance = 1e-10  # Match working code

        # Solve
        summary = pyceres.SolverSummary()
        pyceres.solve(options, problem, summary)

        logger.info(f"Optimization complete: Cost {summary.initial_cost:.2f} -> {summary.final_cost:.2f}")
        logger.info(f"Iterations: {summary.num_successful_steps}")
        logger.info(f"Termination: {summary.termination_type}")

        # Copy optimized values back
        for camera_id in camera_ids:
            self.camera_parameters[camera_id].extrinsics[0:3] = rvec_by_id[camera_id]
            self.camera_parameters[camera_id].extrinsics[3:6] = tvec_by_id[camera_id]

        # Return optimized transforms
        return {
            cid: params.to_transformation_matrix(reference_frame=f"camera-{self.principal_camera_id}")
            for cid, params in self.camera_parameters.items()
        }
