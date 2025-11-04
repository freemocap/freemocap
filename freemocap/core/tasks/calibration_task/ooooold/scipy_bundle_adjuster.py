import logging

import cv2
import numpy as np
from pydantic import BaseModel, Field
from scipy.optimize import least_squares
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.tasks.calibration_task.ooooold.calibration_helpers.camera_math_models import (
    CameraMatrix,
    CameraDistortionCoefficients,
    TransformationMatrix,
)
from freemocap.core.tasks.calibration_task.shared_view_accumulator import MultiCameraTargetView

logger = logging.getLogger(__name__)


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


class ScipyBundleAdjuster(BaseModel):
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
    ) -> "ScipyBundleAdjuster":
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

    def _pack_parameters(self, camera_ids: list[CameraIdString], extrinsics_by_id: dict[CameraIdString, np.ndarray]) -> np.ndarray:
        """Pack all camera extrinsics into a single parameter vector."""
        params = []
        for camera_id in camera_ids:
            if camera_id != self.principal_camera_id:  # Don't include fixed camera
                params.append(extrinsics_by_id[camera_id])
        return np.concatenate(params) if params else np.array([])

    def _unpack_parameters(self, params: np.ndarray, camera_ids: list[CameraIdString]) -> dict[CameraIdString, np.ndarray]:
        """Unpack parameter vector into camera extrinsics."""
        extrinsics_by_id = {}
        idx = 0
        for camera_id in camera_ids:
            if camera_id == self.principal_camera_id:
                # Principal camera is fixed
                extrinsics_by_id[camera_id] = self.camera_parameters[camera_id].extrinsics.copy()
            else:
                extrinsics_by_id[camera_id] = params[idx:idx+6]
                idx += 6
        return extrinsics_by_id

    def _compute_residuals(
            self,
            params: np.ndarray,
            camera_ids: list[CameraIdString],
            intrinsics_by_id: dict[CameraIdString, tuple[np.ndarray, np.ndarray]],
            multi_camera_views: dict[int, MultiCameraTargetView],
    ) -> np.ndarray:
        """Compute reprojection residuals for all observations."""
        extrinsics_by_id = self._unpack_parameters(params, camera_ids)
        residuals = []

        for mc_view in multi_camera_views.values():
            for camera_id, camera_output in mc_view.camera_node_output_by_camera.items():
                if not camera_output.charuco_observation or camera_output.charuco_observation.charuco_empty:
                    continue

                obs = camera_output.charuco_observation
                camera_matrix, dist_coeffs = intrinsics_by_id[camera_id]
                rvec = extrinsics_by_id[camera_id][0:3]
                tvec = extrinsics_by_id[camera_id][3:6]

                for corner_idx, corner_id in enumerate(obs.detected_charuco_corner_ids):
                    corner_id_int = int(corner_id)
                    if corner_id_int not in self.point_3d_coords:
                        continue

                    # Project point
                    projected, _ = cv2.projectPoints(
                        objectPoints=self.point_3d_coords[corner_id_int].reshape(1, 3),
                        rvec=rvec.reshape(3, 1),
                        tvec=tvec.reshape(3, 1),
                        cameraMatrix=camera_matrix,
                        distCoeffs=dist_coeffs,
                    )

                    # Compute residual
                    observed = obs.detected_charuco_corners_image_coordinates[corner_idx]
                    residuals.append(projected.squeeze()[0] - observed[0])
                    residuals.append(projected.squeeze()[1] - observed[1])

        return np.array(residuals)

    def optimize(
            self,
            multi_camera_views: dict[int, MultiCameraTargetView],
    ) -> dict[CameraIdString, TransformationMatrix]:
        logger.info("Starting scipy bundle adjustment optimization...")

        # Extract parameters
        camera_ids = list(self.camera_parameters.keys())
        extrinsics_by_id: dict[CameraIdString, np.ndarray] = {}
        intrinsics_by_id: dict[CameraIdString, tuple[np.ndarray, np.ndarray]] = {}

        for camera_id in camera_ids:
            params = self.camera_parameters[camera_id]
            extrinsics_by_id[camera_id] = params.extrinsics.copy()
            camera_matrix = params.to_camera_matrix()
            dist_coeffs = params.to_distortion_coefficients()
            intrinsics_by_id[camera_id] = (camera_matrix, dist_coeffs)

        # Pack initial parameters
        x0 = self._pack_parameters(camera_ids, extrinsics_by_id)

        # Compute initial residuals
        initial_residuals = self._compute_residuals(x0, camera_ids, intrinsics_by_id, multi_camera_views)
        initial_cost = 0.5 * np.sum(initial_residuals**2)
        num_residuals = len(initial_residuals)
        
        logger.info(f"Initial cost: {initial_cost:.2f} ({num_residuals} residuals)")

        # Run optimization
        result = least_squares(
            fun=lambda params: self._compute_residuals(params, camera_ids, intrinsics_by_id, multi_camera_views),
            x0=x0,
            method='trf',  # Trust Region Reflective - robust and good for large residual problems
            verbose=2,
            max_nfev=100,  # Max function evaluations
            ftol=1e-6,
            gtol=1e-10,
            xtol=1e-8,
        )

        final_cost = 0.5 * np.sum(result.fun**2)
        logger.info(f"Optimization complete: Cost {initial_cost:.2f} -> {final_cost:.2f}")
        logger.info(f"Success: {result.success}, Message: {result.message}")
        logger.info(f"Function evaluations: {result.nfev}")

        # Unpack optimized parameters
        optimized_extrinsics = self._unpack_parameters(result.x, camera_ids)

        # Update camera parameters
        for camera_id in camera_ids:
            self.camera_parameters[camera_id].extrinsics[:] = optimized_extrinsics[camera_id]

        # Return optimized transforms
        return {
            cid: params.to_transformation_matrix(reference_frame=f"camera-{self.principal_camera_id}")
            for cid, params in self.camera_parameters.items()
        }
