from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.tasks.calibration_task.ooooold.calibration_helpers.camera_math_models import \
    CameraDistortionCoefficients, \
    CameraMatrix
from freemocap.pubsub.pubsub_topics import CameraNodeOutputMessage


def _triangulate_batch(
        points2d: np.ndarray,
        projection_matrices: np.ndarray,
) -> np.ndarray:
    """
    Vectorized triangulation using Direct Linear Transform (DLT) method.

    DLT constructs a homogeneous linear system AX=0 where each camera contributes 2 rows:

        For N cameras observing point X=[X,Y,Z,1]ᵀ:

        Camera 0:  [x₀·P₃ - P₁]     [X]
                   [y₀·P₃ - P₂]     [Y]
        Camera 1:  [x₁·P₃ - P₁]  ×  [Z]  = 0
                   [y₁·P₃ - P₂]     [1]
           ⋮             ⋮
        Camera N:  [xₙ·P₃ - P₁]
                   [yₙ·P₃ - P₂]

        Matrix A is (2N × 4), where P₁, P₂, P₃ are rows of projection matrix P.

    Solution via SVD: A = UΣVᵀ, take last row of V (min singular value), normalize by w:
        [X, Y, Z, w]ᵀ → (X/w, Y/w, Z/w)

    :param points2d: Shape (M, N, 2) - M points observed by N cameras (pixel coordinates)
    :param projection_matrices: Shape (N, 3, 4) - full projection matrices P = K[R|t]
    :param preallocated_arrays: Optional pre-allocated arrays (auto-resizes if needed)
    :return: Shape (M, 3) - triangulated 3D positions in world coordinates
    """
    num_points = points2d.shape[0]
    num_cameras = projection_matrices.shape[0]

    A_matrices = np.zeros((num_points, num_cameras * 2, 4), dtype=np.float64)
    points3d_output = np.empty((num_points, 3), dtype=np.float64)

    # Zero out A_matrices in case we're reusing pre-allocated array
    A_matrices.fill(0.0)

    # Build all A matrices at once
    for cam_idx in range(num_cameras):
        x = points2d[:, cam_idx, 0]  # All points, this camera, x coord
        y = points2d[:, cam_idx, 1]  # All points, this camera, y coord
        mat = projection_matrices[cam_idx]

        # Vectorized construction
        A_matrices[:, cam_idx * 2] = x[:, None] * mat[2] - mat[0]
        A_matrices[:, cam_idx * 2 + 1] = y[:, None] * mat[2] - mat[1]

    # Batch SVD on all matrices at once
    _, _, vh = np.linalg.svd(A_matrices, full_matrices=False)

    # Extract last row of vh for each point
    points3d_h = vh[:, -1, :]  # Shape: (num_points, 4)

    # Normalize by w and write directly to output array
    points3d_output[:] = points3d_h[:, :3] / points3d_h[:, 3:4]

    return points3d_output


@dataclass
class CameraCalibrationData:
    """Camera calibration parameters for a single camera."""

    name: str
    image_size: tuple[int, int]  # (width, height)
    matrix: CameraMatrix
    distortion: CameraDistortionCoefficients
    rotation_vector: np.ndarray  # 3x1 Rodrigues rotation vector
    translation: np.ndarray  # 3x1 XYZ translation vector
    world_position: np.ndarray = field(init=False)
    world_orientation: np.ndarray = field(init=False)

    @classmethod
    def from_dict(cls, camera_id: str, data: dict) -> "CameraCalibrationData":
        """Create from dictionary (e.g., loaded from TOML)."""
        if 'image_size' in data:
            image_size_list = data["image_size"]
        elif 'size' in data:
            image_size_list = data["size"]
        else:
            raise KeyError("Camera calibration data must contain 'size' or 'image_size' key")

        if len(image_size_list) != 2:
            raise ValueError(f"Expected size to have 2 elements, got {len(image_size_list)}")

        return cls(
            name=camera_id,
            image_size=(int(image_size_list[0]), int(image_size_list[1])),
            matrix=CameraMatrix(matrix=np.asarray(data["matrix"])),
            distortion=CameraDistortionCoefficients(coefficients=data["distortions"]),
            rotation_vector=np.array(data["rotation"], dtype=np.float64),
            translation=np.array(data["translation"], dtype=np.float64),
        )

    def __post_init__(self) -> None:
        """Validate shapes and compute world coordinates after initialization."""
        if self.matrix.matrix.shape != (3, 3):
            raise ValueError(f"Expected matrix shape (3, 3), got {self.matrix.matrix.shape}")
        if self.distortion.coefficients.shape != (5,):
            raise ValueError(f"Expected distortion shape (5,), got {self.distortion.coefficients.shape}")
        if self.rotation_vector.shape != (3,):
            raise ValueError(f"Expected rotation_vector shape (3,), got {self.rotation_vector.shape}")
        if self.translation.shape != (3,):
            raise ValueError(f"Expected translation shape (3,), got {self.translation.shape}")

        rotation_matrix = self.rotation_matrix
        object.__setattr__(self, 'world_position', -rotation_matrix.T @ self.translation)
        object.__setattr__(self, 'world_orientation', rotation_matrix.T)

    @property
    def rotation_matrix(self) -> np.ndarray:
        """Convert Rodrigues rotation vector to 3x3 rotation matrix."""
        return cv2.Rodrigues(self.rotation_vector)[0]

    @property
    def extrinsics_matrix(self) -> np.ndarray:
        """Extrinsic matrix [R|t] of shape (3, 4)."""
        extrinsics = np.zeros((3, 4), dtype=np.float64)
        extrinsics[:, :3] = self.rotation_matrix
        extrinsics[:, 3] = self.translation
        return extrinsics

    @property
    def projection_matrix(self) -> np.ndarray:
        """Full projection matrix P = K[R|t] of shape (3, 4)."""
        return self.matrix.matrix @ self.extrinsics_matrix

    def undistort_points(self, points: np.ndarray) -> np.ndarray:
        """
        Undistort 2D points and normalize to camera coordinates.

        :param points: Shape (N, 2) or (N, 1, 2) - distorted pixel coordinates
        :return: Shape (N, 2) - undistorted normalized coordinates
        """
        original_shape = points.shape
        points = points.reshape(-1, 1, 2)
        undistorted = cv2.undistortPoints(
            points,
            self.matrix.matrix.astype(np.float64),
            self.distortion.coefficients.astype(np.float64)
        )
        return undistorted.reshape(original_shape)

    def project_3d_to_2d(self, points3d: np.ndarray) -> np.ndarray:
        """
        Project 3D points to 2D image coordinates (with distortion).

        :param points3d: Shape (N, 3) - 3D world coordinates
        :return: Shape (N, 2) - 2D pixel coordinates
        """
        points3d = points3d.reshape(-1, 1, 3)
        projected, _ = cv2.projectPoints(
            points3d,
            self.rotation_vector,
            self.translation,
            self.matrix.matrix,
            self.distortion.coefficients
        )
        return np.squeeze(projected, axis=1)


@dataclass
class PointTriangulator:
    """
    Fast triangulator for high-framerate multi-camera 3D reconstruction.

    Supports both array-based (fast) and dictionary-based (convenient) APIs.
    """

    camera_calibrations: dict[str, CameraCalibrationData]
    projection_matrices: np.ndarray = field(init=False)
    camera_names: list[str] = field(init=False)
    num_cameras: int = field(init=False)

    @classmethod
    def from_toml(cls, toml_path: str | Path) -> "PointTriangulator":
        """
        Load camera calibrations from TOML file.

        :param toml_path: Path to calibration TOML file
        :return: Initialized Triangulator
        """
        import toml

        calibration_data = toml.load(toml_path)
        calibration_data.pop("metadata", None)

        camera_calibrations = {
            camera_id: CameraCalibrationData.from_dict(camera_id, data)
            for camera_id, data in calibration_data.items()
        }

        return cls(camera_calibrations=camera_calibrations)

    def __post_init__(self) -> None:
        """Validate and prepare projection matrices after initialization."""
        if not self.camera_calibrations:
            raise ValueError("camera_calibrations cannot be empty")

        self.num_cameras = len(self.camera_calibrations)
        self.camera_names = list(self.camera_calibrations.keys())

        projection_matrices = np.array(
            [cam.projection_matrix for cam in self.camera_calibrations.values()],
            dtype=np.float64
        )

        if projection_matrices.shape != (self.num_cameras, 3, 4):
            raise ValueError(
                f"Expected projection matrices shape ({self.num_cameras}, 3, 4), "
                f"got {projection_matrices.shape}"
            )

        object.__setattr__(
            self,
            'projection_matrices',
            np.ascontiguousarray(projection_matrices, dtype=np.float64)
        )

    def triangulate_camera_node_outputs(
            self,
            camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage],
            undistort_points: bool = True,
            compute_reprojection_error: bool = False
    ) -> tuple[np.ndarray, np.ndarray | None]:
        """
        Triangulate 3D points from camera node outputs containing charuco observations.

        :param camera_node_outputs: Dictionary mapping camera IDs to their output messages
        :param undistort_points: If True, undistort points before triangulation
        :param compute_reprojection_error: Whether to compute reprojection errors
        :return: Tuple of (points3d, mean_errors)
                 - points3d: Shape (M, 3) - triangulated 3D points for each charuco corner
                 - mean_errors: Shape (M,) - mean reprojection error per point (pixels), or None
        """
        points2d_list: list[np.ndarray] = []

        for camera_name in self.camera_names:
            if camera_name not in camera_node_outputs:
                raise ValueError(f"Camera '{camera_name}' not found in camera_node_outputs")

            camera_output = camera_node_outputs[camera_name]

            if camera_output.charuco_observation is None:
                raise ValueError(f"Camera '{camera_name}' has no charuco_observation")

            points2d_camera = camera_output.charuco_observation.to_2d_array()
            points2d_list.append(points2d_camera)

        points2d_stacked = np.stack(points2d_list, axis=0)
        points2d = np.transpose(points2d_stacked, (1, 0, 2))

        return self.triangulate_points(
            points2d=points2d,
            undistort_points=undistort_points,
            compute_reprojection_error=compute_reprojection_error
        )

    def triangulate_points(
            self,
            points2d: np.ndarray,
            undistort_points: bool = False,
            compute_reprojection_error: bool = True
    ) -> tuple[np.ndarray, np.ndarray | None]:
        """
        Fast array-based triangulation for batch processing.

        :param points2d: Shape (M, N, 2) - M points observed by N cameras (pixel coordinates)
        :param preallocated_arrays: Optional pre-allocated arrays (auto-resizes if needed)
        :param undistort_points: If True, undistort points before triangulation
        :param compute_reprojection_error: Whether to compute reprojection errors
        :return: Tuple of (points3d, mean_errors)
                 - points3d: Shape (M, 3) - triangulated 3D points
                 - mean_errors: Shape (M,) - mean reprojection error per point (pixels), or None
        """
        if points2d.ndim != 3 or points2d.shape[2] != 2:
            raise ValueError(f"points2d must have shape (M, N, 2), got {points2d.shape}")

        if points2d.shape[1] != self.num_cameras:
            raise ValueError(
                f"points2d has {points2d.shape[1]} cameras but triangulator "
                f"has {self.num_cameras} cameras"
            )

        points2d = np.ascontiguousarray(points2d, dtype=np.float64)

        if undistort_points:
            for cam_idx, cam_calib in enumerate(self.camera_calibrations.values()):
                points2d[:, cam_idx] = cam_calib.undistort_points(points2d[:, cam_idx])

        points3d = _triangulate_batch(
            points2d,
            self.projection_matrices,
        )

        mean_errors = None
        if compute_reprojection_error:
            mean_errors = self._compute_reprojection_errors(points3d, points2d)

        return points3d, mean_errors

    def _compute_reprojection_errors(
            self,
            points3d: np.ndarray,
            points2d: np.ndarray
    ) -> np.ndarray:
        """
        Compute reprojection errors using OpenCV's projection (handles distortion).

        :param points3d: Shape (M, 3) - triangulated 3D points
        :param points2d: Shape (M, N, 2) - original 2D observations
        :return: Shape (M,) - mean reprojection error per point across all cameras
        """
        num_points = points3d.shape[0]
        errors = np.zeros(num_points, dtype=np.float64)

        for point_idx in range(num_points):
            point_errors = []

            for cam_idx, (cam_name, cam_calib) in enumerate(self.camera_calibrations.items()):
                projected = cam_calib.project_3d_to_2d(points3d[point_idx:point_idx + 1])
                diff = projected[0] - points2d[point_idx, cam_idx]
                error = np.linalg.norm(diff)
                point_errors.append(error)

            errors[point_idx] = np.mean(point_errors)

        return errors

    def triangulate_dict(
            self,
            points2d_by_camera: dict[str, dict[str, tuple[float, float]]],
            min_cameras: int = 2,
            compute_reprojection_error: bool = False
    ) -> dict[str, tuple[float, float, float] | dict]:
        """
        Dictionary-based triangulation (backward compatible API).

        :param points2d_by_camera: {camera_name: {point_name: (x, y)}}
        :param min_cameras: Minimum number of cameras required to triangulate a point
        :param compute_reprojection_error: If True, return dict with 'point' and 'error' keys
        :return: {point_name: (x, y, z)} or {point_name: {'point': (x,y,z), 'error': float}}
        """
        if not points2d_by_camera:
            return {}

        first_camera = next(iter(points2d_by_camera.values()))
        point_names = list(first_camera.keys())

        for cam_name, points in points2d_by_camera.items():
            if list(points.keys()) != point_names:
                raise ValueError(f"Camera {cam_name} has different point names")

        results = {}

        for point_name in point_names:
            observations = []
            valid_camera_indices = []

            for cam_idx, cam_name in enumerate(self.camera_names):
                if cam_name not in points2d_by_camera:
                    continue

                point2d = points2d_by_camera[cam_name].get(point_name)
                if point2d is None:
                    continue

                if np.isnan(point2d).any():
                    continue

                observations.append(point2d)
                valid_camera_indices.append(cam_idx)

            if len(observations) < min_cameras:
                results[point_name] = (np.nan, np.nan, np.nan)
                continue

            points2d_array = np.array([observations], dtype=np.float64)
            valid_projection_matrices = self.projection_matrices[valid_camera_indices]

            point3d = _triangulate_batch(points2d_array, valid_projection_matrices)[0]

            if compute_reprojection_error:
                errors = []
                for cam_idx, obs in zip(valid_camera_indices, observations):
                    cam_name = self.camera_names[cam_idx]
                    cam_calib = self.camera_calibrations[cam_name]
                    projected = cam_calib.project_3d_to_2d(point3d.reshape(1, 3))
                    error = np.linalg.norm(projected[0] - np.array(obs))
                    errors.append(error)

                results[point_name] = {
                    'point': tuple(point3d),
                    'error': float(np.mean(errors))
                }
            else:
                results[point_name] = tuple(point3d)

        return results


def benchmark_triangulator() -> None:
    # TODO : implement benchmark
    pass


if __name__ == "__main__":
    benchmark_triangulator()
