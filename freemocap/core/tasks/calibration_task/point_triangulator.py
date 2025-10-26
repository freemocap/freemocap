from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from skellycam.core.types.type_overloads import CameraIdString
from freemocap.core.pubsub.pubsub_topics import CameraNodeOutputMessage


def _triangulate_batch(points2d: np.ndarray, projection_matrices: np.ndarray) -> np.ndarray:
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
    :return: Shape (M, 3) - triangulated 3D positions in world coordinates
    """
    num_points = points2d.shape[0]
    num_cameras = projection_matrices.shape[0]

    # Build all A matrices at once: shape (num_points, 2*num_cameras, 4)
    A_matrices = np.zeros((num_points, num_cameras * 2, 4), dtype=np.float64)

    for cam_idx in range(num_cameras):
        x = points2d[:, cam_idx, 0]  # All points, this camera, x coord
        y = points2d[:, cam_idx, 1]  # All points, this camera, y coord
        mat = projection_matrices[cam_idx]

        # Vectorized construction
        A_matrices[:, cam_idx * 2] = x[:, None] * mat[2] - mat[0]
        A_matrices[:, cam_idx * 2 + 1] = y[:, None] * mat[2] - mat[1]

    # Batch SVD on all matrices at once!
    _, _, vh = np.linalg.svd(A_matrices, full_matrices=False)

    # Extract last row of vh for each point
    points3d_h = vh[:, -1, :]  # Shape: (num_points, 4)

    # Normalize by w
    points3d = points3d_h[:, :3] / points3d_h[:, 3:4]

    return points3d
@dataclass
class CameraCalibrationData:
    """Camera calibration parameters for a single camera."""

    name: str
    image_size: tuple[int, int] # (width, height)
    matrix: np.ndarray  # 3x3 intrinsic matrix K
    distortion: np.ndarray  # 1x5 distortion coefficients
    rotation_vector: np.ndarray  # 3x1 Rodrigues rotation vector
    translation: np.ndarray  # 3x1 XYZ translation vector
    world_position: np.ndarray = field(init=False)  # 3D position in world coordinates - computed in __post_init__
    world_orientation: np.ndarray = field(init=False)  # 3x3 rotation matrix in world coordinates - computed in __post_init__

    @classmethod
    def from_dict(cls, camera_id: str, data: dict) -> "CameraCalibrationData":
        """Create from dictionary (e.g., loaded from TOML)."""
        if 'image_size' in data:
            image_size_list = data["image_size"]
        elif 'size' in data: # for backward compatibility with anipose format
            image_size_list = data["size"]
        else:
            raise KeyError("Camera calibration data must contain 'size' or 'image_size' key")
        if len(image_size_list) != 2:
            raise ValueError(f"Expected size to have 2 elements, got {len(image_size_list)}")
        return cls(
            name=camera_id,
            image_size=(int(image_size_list[0]), int(image_size_list[1])),
            matrix=np.array(data["matrix"], dtype=np.float64),
            distortion=np.array(data["distortions"], dtype=np.float64),
            rotation_vector=np.array(data["rotation"], dtype=np.float64),
            translation=np.array(data["translation"], dtype=np.float64),
        )

    def __post_init__(self) -> None:
        """Validate shapes and compute world coordinates after initialization."""
        if self.matrix.shape != (3, 3):
            raise ValueError(f"Expected matrix shape (3, 3), got {self.matrix.shape}")
        if self.distortion.shape != (5,):
            raise ValueError(f"Expected distortion shape (5,), got {self.distortion.shape}")
        if self.rotation_vector.shape != (3,):
            raise ValueError(f"Expected rotation_vector shape (3,), got {self.rotation_vector.shape}")
        if self.translation.shape != (3,):
            raise ValueError(f"Expected translation shape (3,), got {self.translation.shape}")

        # Compute world coordinates (camera position and orientation in world space)
        # world coordinates = inverse of camera extrinsics
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
        return self.matrix @ self.extrinsics_matrix

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
            self.matrix.astype(np.float64),
            self.distortion.astype(np.float64)
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
            self.matrix,
            self.distortion
        )
        return np.squeeze(projected, axis=1)


@dataclass
class PointTriangulator:
    """
    Fast triangulator for high-framerate multi-camera 3D reconstruction.

    Supports both array-based (fast) and dictionary-based (convenient) APIs.
    """

    camera_calibrations: dict[str, CameraCalibrationData]
    projection_matrices: np.ndarray = field(init=False) #pre-extracted from calibration data in post-init (for speed)
    camera_names: list[str] = field(init=False) #pre-extracted from calibration data in post-init (for speed)
    num_cameras: int = field(init=False) #pre-extracted from calibration data in post-init (for speed)

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

        # Pre-compute full projection matrices P = K[R|t]
        # This allows triangulation with pixel coordinates directly (no undistortion needed)
        projection_matrices = np.array(
            [cam.projection_matrix for cam in self.camera_calibrations.values()],
            dtype=np.float64
        )

        if projection_matrices.shape != (self.num_cameras, 3, 4):
            raise ValueError(f"Expected projection matrices shape ({self.num_cameras}, 3, 4), "
                             f"got {projection_matrices.shape}")

        object.__setattr__(self, 'projection_matrices',
                           np.ascontiguousarray(projection_matrices, dtype=np.float64))

        # Pre-compile JIT functions
        self._warmup()

    def _warmup(self) -> None:
        """Pre-compile JIT functions to avoid first-call overhead."""
        dummy_points = np.random.rand(2, self.num_cameras, 2).astype(np.float64)
        _ = _triangulate_batch(dummy_points, self.projection_matrices)

    def triangulate_camera_node_outputs(self,
                                        camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage],
                                        undistort_points: bool = True,
                                        compute_reprojection_error: bool = False) -> tuple[
        np.ndarray, np.ndarray | None]:
        """
        Triangulate 3D points from camera node outputs containing charuco observations.

        :param camera_node_outputs: Dictionary mapping camera IDs to their output messages
        :param undistort_points: If True, undistort points before triangulation
        :param compute_reprojection_error: Whether to compute reprojection errors
        :return: Tuple of (points3d, mean_errors)
                 - points3d: Shape (M, 3) - triangulated 3D points for each charuco corner
                 - mean_errors: Shape (M,) - mean reprojection error per point (pixels), or None
        """
        # Extract 2D points for each camera in the correct order
        points2d_list: list[np.ndarray] = []

        for camera_name in self.camera_names:
            if camera_name not in camera_node_outputs:
                raise ValueError(f"Camera '{camera_name}' not found in camera_node_outputs")

            camera_output = camera_node_outputs[camera_name]

            if camera_output.charuco_observation is None:
                raise ValueError(f"Camera '{camera_name}' has no charuco_observation")

            # Get 2D array of shape (num_charuco_corners, 2)
            # Non-detected corners will be np.nan
            points2d_camera = camera_output.charuco_observation.to_2d_array()
            points2d_list.append(points2d_camera)

        # Stack along new axis to get shape (num_cameras, num_charuco_corners, 2)
        points2d_stacked = np.stack(points2d_list, axis=0)

        # Transpose to get shape (num_charuco_corners, num_cameras, 2)
        points2d = np.transpose(points2d_stacked, (1, 0, 2))

        # Use the existing triangulate_points method
        return self.triangulate_points(
            points2d=points2d,
            undistort_points=undistort_points,
            compute_reprojection_error=compute_reprojection_error
        )
    def triangulate_points(self,
                                        points2d: np.ndarray,
                                        undistort_points: bool = False,
                                        compute_reprojection_error: bool = True) -> tuple[np.ndarray, np.ndarray | None]:
        """
        Fast array-based triangulation for batch processing.

        :param points2d: Shape (M, N, 2) - M points observed by N cameras (pixel coordinates)
        :param compute_reprojection_error: Whether to compute reprojection errors
        :param undistort_points: If True, undistort points before triangulation
        :return: Tuple of (points3d, mean_errors)
                 - points3d: Shape (M, 3) - triangulated 3D points
                 - mean_errors: Shape (M,) - mean reprojection error per point (pixels), or None
        """
        if points2d.ndim != 3 or points2d.shape[2] != 2:
            raise ValueError(f"points2d must have shape (M, N, 2), got {points2d.shape}")

        if points2d.shape[1] != self.num_cameras:
            raise ValueError(f"points2d has {points2d.shape[1]} cameras but triangulator "
                             f"has {self.num_cameras} cameras")

        points2d = np.ascontiguousarray(points2d, dtype=np.float64)

        if undistort_points:
            for cam_idx, cam_calib in enumerate(self.camera_calibrations.values()):
                points2d[:, cam_idx] = cam_calib.undistort_points(points2d[:, cam_idx])

        # Triangulate using full projection matrices
        points3d = _triangulate_batch(points2d, self.projection_matrices)

        # Compute reprojection errors if requested
        mean_errors = None
        if compute_reprojection_error:
            mean_errors = self._compute_reprojection_errors(points3d, points2d)

        return points3d, mean_errors

    def _compute_reprojection_errors(self,
                                     points3d: np.ndarray,
                                     points2d: np.ndarray) -> np.ndarray:
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
                # Project 3D point back to 2D using OpenCV (handles distortion)
                projected = cam_calib.project_3d_to_2d(points3d[point_idx:point_idx + 1])

                # Compute Euclidean distance
                diff = projected[0] - points2d[point_idx, cam_idx]
                error = np.linalg.norm(diff)
                point_errors.append(error)

            errors[point_idx] = np.mean(point_errors)

        return errors

    def triangulate_dict(self,
                         points2d_by_camera: dict[str, dict[str, tuple[float, float]]],
                         min_cameras: int = 2,
                         compute_reprojection_error: bool = False) -> dict[str, tuple[float, float, float] | dict]:
        """
        Dictionary-based triangulation (backward compatible API).

        :param points2d_by_camera: {camera_name: {point_name: (x, y)}}
        :param min_cameras: Minimum number of cameras required to triangulate a point
        :param compute_reprojection_error: If True, return dict with 'point' and 'error' keys
        :return: {point_name: (x, y, z)} or {point_name: {'point': (x,y,z), 'error': float}}
        """
        if not points2d_by_camera:
            return {}

        # Get point names from first camera
        first_camera = next(iter(points2d_by_camera.values()))
        point_names = list(first_camera.keys())

        # Validate all cameras have same point names
        for cam_name, points in points2d_by_camera.items():
            if list(points.keys()) != point_names:
                raise ValueError(f"Camera {cam_name} has different point names")

        results = {}

        for point_name in point_names:
            # Collect observations for this point
            observations = []
            valid_camera_indices = []

            for cam_idx, cam_name in enumerate(self.camera_names):
                if cam_name not in points2d_by_camera:
                    continue

                point2d = points2d_by_camera[cam_name].get(point_name)
                if point2d is None:
                    continue

                # Check for NaN
                if np.isnan(point2d).any():
                    continue

                observations.append(point2d)
                valid_camera_indices.append(cam_idx)

            # Skip if not enough cameras
            if len(observations) < min_cameras:
                results[point_name] = (np.nan, np.nan, np.nan)
                continue

            # Build arrays for triangulation
            points2d_array = np.array([observations], dtype=np.float64)  # Shape: (1, N, 2)
            valid_projection_matrices = self.projection_matrices[valid_camera_indices]

            # Triangulate
            point3d = _triangulate_batch(points2d_array, valid_projection_matrices)[0]

            if compute_reprojection_error:
                # Compute error only for valid cameras
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
    # Example usage
    if __name__ == "__main__":
        import time
        from typing import Any

        print("=" * 80)
        print("TRIANGULATOR PERFORMANCE BENCHMARK")
        print("=" * 80)

        # Create synthetic camera calibrations with realistic distortion
        num_cameras: int = 4
        camera_calibrations: dict[str, CameraCalibrationData] = {}

        for i in range(num_cameras):
            # Add realistic distortion coefficients
            distortion = np.array([
                -0.2 + np.random.randn() * 0.05,  # k1
                0.1 + np.random.randn() * 0.02,  # k2
                np.random.randn() * 0.001,  # p1
                np.random.randn() * 0.001,  # p2
                np.random.randn() * 0.01  # k3
            ], dtype=np.float64)

            camera_calibrations[f"cam_{i}"] = CameraCalibrationData(
                name=f"cam_{i}",
                image_size=(1920, 1080),
                matrix=np.eye(3, dtype=np.float64) * 1000,
                distortion=distortion,
                rotation_vector=np.random.randn(3).astype(np.float64) * 0.1,
                translation=np.random.randn(3).astype(np.float64) * 0.5,
            )

        # Initialize triangulator
        triangulator = PointTriangulator(camera_calibrations=camera_calibrations)
        print(f"\nTriangulator initialized with {num_cameras} cameras")
        print("Using FULL projection matrices P = K[R|t]")
        print("Cameras have realistic lens distortion parameters\n")

        # Generate test data once for fair comparison
        num_test_points: int = 100
        test_points_2d = np.random.rand(num_test_points, num_cameras, 2).astype(np.float64) * 1000

        # Convert to dict format for dict-based method
        test_points_dict: dict[str, dict[str, tuple[float, float]]] = {
            f"cam_{cam_idx}": {
                f"point_{pt_idx}": (
                    float(test_points_2d[pt_idx, cam_idx, 0]),
                    float(test_points_2d[pt_idx, cam_idx, 1])
                )
                for pt_idx in range(num_test_points)
            }
            for cam_idx in range(num_cameras)
        }

        print("=" * 80)
        print("TEST 1: HEAD-TO-HEAD COMPARISON (Same Data)")
        print("=" * 80)
        print(f"Points: {num_test_points}")
        print(f"Cameras: {num_cameras}")
        print()

        # Warmup all configurations
        for undistort in [False, True]:
            for compute_error in [False, True]:
                _ = triangulator.triangulate_camera_node_outputs(
                    points2d=test_points_2d,
                    undistort_points=undistort,
                    compute_reprojection_error=compute_error
                )
        _ = triangulator.triangulate_dict(
            points2d_by_camera=test_points_dict,
            compute_reprojection_error=False
        )

        # Test all configurations
        num_iterations: int = 100
        configs: list[tuple[bool, bool, str]] = [
            (False, False, "Fast (no undistort, no error)"),
            (True, False, "With undistortion only"),
            (False, True, "With reprojection error only"),
            (True, True, "Full (undistort + error)"),
        ]

        print("Array-based method performance:")
        print("-" * 80)
        array_times: dict[tuple[bool, bool], float] = {}

        for undistort, compute_error, label in configs:
            start = time.perf_counter()
            for _ in range(num_iterations):
                _, _ = triangulator.triangulate_camera_node_outputs(
                    points2d=test_points_2d,
                    undistort_points=undistort,
                    compute_reprojection_error=compute_error
                )
            avg_time = (time.perf_counter() - start) / num_iterations
            array_times[(undistort, compute_error)] = avg_time

            print(f"{label:40s}: {avg_time * 1000:7.3f} ms  ({num_test_points / avg_time:8.0f} pts/sec)")

        # Dict-based method (for reference)
        start = time.perf_counter()
        for _ in range(num_iterations):
            _ = triangulator.triangulate_dict(
                points2d_by_camera=test_points_dict,
                compute_reprojection_error=False
            )
        dict_time = (time.perf_counter() - start) / num_iterations

        print(
            f"\nDict-based method (for reference):      {dict_time * 1000:7.3f} ms  ({num_test_points / dict_time:8.0f} pts/sec)")
        print(f"Array vs Dict speedup:                   {dict_time / array_times[(False, False)]:.1f}x")

        # Show overhead breakdown
        base_time = array_times[(False, False)]
        undistort_overhead = array_times[(True, False)] - base_time
        error_overhead = array_times[(False, True)] - base_time

        print(f"\nOverhead analysis:")
        print(f"  Base triangulation:      {base_time * 1000:.3f} ms")
        print(
            f"  Undistortion overhead:   {undistort_overhead * 1000:.3f} ms (+{undistort_overhead / base_time * 100:.1f}%)")
        print(f"  Error calc overhead:     {error_overhead * 1000:.3f} ms (+{error_overhead / base_time * 100:.1f}%)")

        print("\n" + "=" * 80)
        print("TEST 2: FIND MAXIMUM POINTS FOR 30ms WINDOW")
        print("=" * 80)

        target_time_ms: float = 30.0
        target_time_s: float = target_time_ms / 1000.0

        # Test configurations for 30ms budget
        budget_configs: list[tuple[bool, bool, str]] = [
            (False, False, "Fastest (no undistort, no error)"),
            (True, False, "With undistortion"),
            (False, True, "With error calc"),
            (True, True, "Full pipeline"),
        ]

        points_to_test: list[int] = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]

        # Store results for each configuration
        config_results: dict[tuple[bool, bool], list[tuple[int, float]]] = {
            config[:2]: [] for config in budget_configs
        }

        print(f"\nTesting point counts to find 30ms threshold...")
        print(f"{'Points':>8s}  {'Fast':>10s}  {'Undistort':>10s}  {'Error':>10s}  {'Full':>10s}")
        print("-" * 60)

        for num_points in points_to_test:
            test_data = np.random.rand(num_points, num_cameras, 2).astype(np.float64) * 1000

            times: list[float] = []
            for undistort, compute_error, _ in budget_configs:
                start = time.perf_counter()
                _, _ = triangulator.triangulate_camera_node_outputs(
                    points2d=test_data,
                    undistort_points=undistort,
                    compute_reprojection_error=compute_error
                )
                elapsed = time.perf_counter() - start
                config_results[(undistort, compute_error)].append((num_points, elapsed))
                times.append(elapsed)

            # Print row
            times_str = "  ".join([f"{t * 1000:>8.2f}ms" for t in times])
            print(f"{num_points:8d}  {times_str}")

            # Stop if all configs exceed 2x the target
            if all(t > target_time_s * 2 for t in times):
                break

        print("\n" + "=" * 80)
        print("SUMMARY: 30ms BUDGET ANALYSIS")
        print("=" * 80)

        for undistort, compute_error, label in budget_configs:
            results = config_results[(undistort, compute_error)]

            # Find max points within budget
            max_points_in_budget: int = 0
            for num_points, elapsed in results:
                if elapsed <= target_time_s:
                    max_points_in_budget = num_points

            # Interpolate for more accurate estimate
            estimated_max: int | None = None
            for i, (num_points, elapsed) in enumerate(results):
                if elapsed > target_time_s:
                    if i > 0:
                        prev_points, prev_time = results[i - 1]
                        # Linear interpolation
                        estimated_max = int(prev_points + (target_time_s - prev_time) /
                                            (elapsed - prev_time) * (num_points - prev_points))
                    break

            print(f"\n{label}:")
            if estimated_max:
                print(f"  Max points in 30ms: ~{estimated_max:,} points")
                print(f"  Throughput:         ~{estimated_max / target_time_s:.0f} points/second")
                print(f"  Effective framerate: {1.0 / target_time_s:.1f} fps @ {estimated_max} points/frame")
            elif max_points_in_budget > 0:
                print(f"  Max points in 30ms: >{max_points_in_budget:,} points")
            else:
                print(f"  Cannot meet 30ms budget (too slow)")

        print("\n" + "=" * 80)
        print("TEST 3: TYPICAL USE CASE SIMULATION")
        print("=" * 80)

        # Simulate different typical scenarios
        scenarios: list[tuple[int, int, bool, bool, str]] = [
            (60, 33, False, True, "60fps @ 33 points (fast tracking)"),
            (30, 50, True, True, "30fps @ 50 points (full pipeline)"),
            (30, 100, False, True, "30fps @ 100 points (no undistort)"),
            (120, 20, False, False, "120fps @ 20 points (ultra-fast)"),
        ]

        for target_fps, points_per_frame, undistort, compute_error, description in scenarios:
            target_frame_time = 1.0 / target_fps
            num_test_frames = max(10, int(target_fps * 0.5))  # Test for 0.5 seconds

            print(f"\n{description}")
            print(f"  Target: {target_frame_time * 1000:.2f}ms per frame")

            frame_times: list[float] = []
            start_total = time.perf_counter()

            for _ in range(num_test_frames):
                frame_points = np.random.rand(points_per_frame, num_cameras, 2).astype(np.float64) * 1000

                frame_start = time.perf_counter()
                _, _ = triangulator.triangulate_camera_node_outputs(
                    points2d=frame_points,
                    undistort_points=undistort,
                    compute_reprojection_error=compute_error
                )
                frame_times.append(time.perf_counter() - frame_start)

            total_time = time.perf_counter() - start_total
            avg_frame_time = np.mean(frame_times)
            max_frame_time = np.max(frame_times)
            achieved_fps = num_test_frames / total_time

            budget_met = "✓" if avg_frame_time <= target_frame_time else "✗"

            print(f"  Result: {budget_met}")
            print(f"  Avg frame time:     {avg_frame_time * 1000:.3f}ms")
            print(f"  Max frame time:     {max_frame_time * 1000:.3f}ms")
            print(f"  Achieved FPS:       {achieved_fps:.1f}")
            print(f"  Throughput:         {points_per_frame * achieved_fps:.0f} points/second")

        print("\n" + "=" * 80)
        print("TEST 4: CAMERA WORLD COORDINATES")
        print("=" * 80)
        for cam_name, cam_calib in triangulator.camera_calibrations.items():
            pos = cam_calib.world_position
            z_axis = cam_calib.world_orientation[:, 2]
            print(f"\n{cam_name}:")
            print(f"  Position: [{pos[0]:7.3f}, {pos[1]:7.3f}, {pos[2]:7.3f}]")
            print(f"  Z-axis:   [{z_axis[0]:7.3f}, {z_axis[1]:7.3f}, {z_axis[2]:7.3f}]")
            print(f"  Distortion: k1={cam_calib.distortion[0]:.4f}, k2={cam_calib.distortion[1]:.4f}")

        print("\n" + "=" * 80)
        print("BENCHMARK COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    benchmark_triangulator()