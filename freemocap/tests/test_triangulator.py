import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest
import toml

from freemocap.core.tasks.calibration_task.ooooold.calibration_helpers.camera_math_models import (
    CameraDistortionCoefficients,
    CameraMatrix,
)
from freemocap.core.tasks.calibration_task.ooooold.point_triangulator import CameraCalibrationData, PointTriangulator


class SyntheticCameraSetup:
    """Helper class to generate synthetic multi-camera calibration data."""

    def __init__(
            self,
            num_cameras: int,
            image_width: int = 1920,
            image_height: int = 1080,
            focal_length: float = 1000.0,
            baseline: float = 0.5,
            noise_std: float = 0.0,
    ):
        self.num_cameras = num_cameras
        self.image_width = image_width
        self.image_height = image_height
        self.focal_length = focal_length
        self.baseline = baseline
        self.noise_std = noise_std

        self.camera_calibrations = self._create_cameras()

    def _create_cameras(self) -> dict[str, CameraCalibrationData]:
        """Create synthetic cameras in a standard stereo/multi-camera configuration."""
        cameras: dict[str, CameraCalibrationData] = {}

        for i in range(self.num_cameras):
            camera_id = f"cam_{i:02d}"

            # Arrange cameras horizontally along X-axis
            # Cameras are evenly spaced and all look in +Z direction
            if self.num_cameras == 1:
                x = 0.0
            else:
                # Spread cameras symmetrically around X=0
                x = (i - (self.num_cameras - 1) / 2) * self.baseline

            y = 0.0
            z = 0.0  # Cameras on the X-Y plane at Z=0

            camera_position = np.array([x, y, z], dtype=np.float64)

            # All cameras look in +Z direction (forward)
            # Standard camera orientation: X right, Y down, Z forward
            rotation_matrix = np.eye(3, dtype=np.float64)

            # Convert rotation matrix to OpenCV rotation vector
            rotation_vector = cv2.Rodrigues(rotation_matrix)[0].ravel()

            # Translation: position of world origin in camera coordinates
            # t = -R @ camera_position
            translation = -rotation_matrix @ camera_position

            # Camera intrinsics
            camera_matrix = CameraMatrix(
                matrix=np.array(
                    [
                        [self.focal_length, 0, self.image_width / 2],
                        [0, self.focal_length, self.image_height / 2],
                        [0, 0, 1],
                    ],
                    dtype=np.float64,
                )
            )

            # No distortion for simplicity
            distortion = CameraDistortionCoefficients(
                coefficients=np.zeros(5, dtype=np.float64)
            )

            cameras[camera_id] = CameraCalibrationData(
                name=camera_id,
                image_size=(self.image_width, self.image_height),
                matrix=camera_matrix,
                distortion=distortion,
                rotation_vector=rotation_vector,
                translation=translation,
            )

        return cameras

    def project_points(
            self, points3d: np.ndarray
    ) -> dict[str, np.ndarray]:
        """
        Project 3D points to 2D in all cameras.

        Args:
            points3d: Shape (N, 3) - 3D world coordinates

        Returns:
            Dictionary mapping camera_id to (N, 2) 2D pixel coordinates
        """
        points2d_by_camera: dict[str, np.ndarray] = {}

        for camera_id, camera in self.camera_calibrations.items():
            points2d = camera.project_3d_to_2d(points3d)

            # Add noise if specified
            if self.noise_std > 0:
                noise = np.random.normal(0, self.noise_std, points2d.shape)
                points2d = points2d + noise

            points2d_by_camera[camera_id] = points2d

        return points2d_by_camera

    def create_toml_file(self, output_path: Path) -> None:
        """Save calibration data to TOML file."""
        toml_data: dict = {}

        for camera_id, camera in self.camera_calibrations.items():
            toml_data[camera_id] = {
                "size": list(camera.image_size),
                "matrix": {"matrix": camera.matrix.matrix.tolist()},
                "distortions": {"coefficients": camera.distortion.coefficients.tolist()},
                "rotation": camera.rotation_vector.tolist(),
                "translation": camera.translation.tolist(),
            }

        with open(output_path, "w") as f:
            toml.dump(toml_data, f)


@pytest.fixture
def synthetic_setup_2_cameras() -> SyntheticCameraSetup:
    """Create a simple 2-camera stereo setup."""
    return SyntheticCameraSetup(num_cameras=2, baseline=0.5, noise_std=0.0)


@pytest.fixture
def synthetic_setup_4_cameras() -> SyntheticCameraSetup:
    """Create a 4-camera setup."""
    return SyntheticCameraSetup(num_cameras=4, baseline=0.3, noise_std=0.0)


@pytest.fixture
def synthetic_setup_with_noise() -> SyntheticCameraSetup:
    """Create a 3-camera setup with realistic noise."""
    return SyntheticCameraSetup(num_cameras=3, baseline=0.4, noise_std=0.5)


@pytest.fixture
def random_3d_points() -> np.ndarray:
    """Generate random 3D points in front of cameras."""
    np.random.seed(42)
    num_points = 20

    # Generate points in a reasonable volume IN FRONT of cameras (positive Z)
    # X and Y spread, Z from 1m to 5m in front
    points3d = np.random.uniform(
        low=[-0.5, -0.5, 1.0], high=[0.5, 0.5, 5.0], size=(num_points, 3)
    )

    return points3d.astype(np.float64)


class TestPointTriangulator:
    """Test suite for PointTriangulator."""

    def test_create_from_dict(self, synthetic_setup_2_cameras: SyntheticCameraSetup) -> None:
        """Test creating triangulator from calibration dict."""
        triangulator = PointTriangulator(
            camera_calibrations=synthetic_setup_2_cameras.camera_calibrations
        )

        assert triangulator.num_cameras == 2
        assert len(triangulator.camera_names) == 2
        assert triangulator.projection_matrices.shape == (2, 3, 4)

    def test_create_from_toml(self, synthetic_setup_4_cameras: SyntheticCameraSetup) -> None:
        """Test loading triangulator from TOML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            toml_path = Path(tmpdir) / "calibration.toml"
            synthetic_setup_4_cameras.create_toml_file(toml_path)

            triangulator = PointTriangulator.from_toml(toml_path)

            assert triangulator.num_cameras == 4
            assert len(triangulator.camera_names) == 4
            assert all(
                name in triangulator.camera_calibrations
                for name in [f"cam_{i:02d}" for i in range(4)]
            )

    def test_triangulation_perfect_conditions(
            self, synthetic_setup_2_cameras: SyntheticCameraSetup, random_3d_points: np.ndarray
    ) -> None:
        """Test triangulation with perfect synthetic data (no noise)."""
        triangulator = PointTriangulator(
            camera_calibrations=synthetic_setup_2_cameras.camera_calibrations
        )

        # Project 3D points to 2D
        points2d_by_camera = synthetic_setup_2_cameras.project_points(random_3d_points)

        # Stack into (M, N, 2) format
        points2d = np.stack(
            [points2d_by_camera[cam_id] for cam_id in triangulator.camera_names], axis=1
        )

        # Triangulate
        triangulated_3d, errors = triangulator.triangulate_points(
            points2d=points2d, undistort_points=False, compute_reprojection_error=True
        )

        # Check shape
        assert triangulated_3d.shape == random_3d_points.shape
        assert errors is not None
        assert errors.shape == (random_3d_points.shape[0],)

        # Check accuracy - should be very accurate with no noise
        max_error = np.max(np.linalg.norm(triangulated_3d - random_3d_points, axis=1))
        assert max_error < 0.01, f"Max reconstruction error: {max_error:.6f}m"

        # Check reprojection errors are small
        assert np.max(errors) < 1.0, f"Max reprojection error: {np.max(errors):.3f} pixels"

    def test_triangulation_multiple_cameras(
            self, synthetic_setup_4_cameras: SyntheticCameraSetup, random_3d_points: np.ndarray
    ) -> None:
        """Test triangulation with 4 cameras improves accuracy."""
        triangulator = PointTriangulator(
            camera_calibrations=synthetic_setup_4_cameras.camera_calibrations
        )

        points2d_by_camera = synthetic_setup_4_cameras.project_points(random_3d_points)

        points2d = np.stack(
            [points2d_by_camera[cam_id] for cam_id in triangulator.camera_names], axis=1
        )

        triangulated_3d, errors = triangulator.triangulate_points(
            points2d=points2d, undistort_points=False, compute_reprojection_error=True
        )

        # More cameras should give better accuracy
        max_error = np.max(np.linalg.norm(triangulated_3d - random_3d_points, axis=1))
        assert max_error < 0.005, f"Max reconstruction error: {max_error:.6f}m"

        mean_reprojection_error = np.mean(errors)
        assert mean_reprojection_error < 0.5, f"Mean reprojection error: {mean_reprojection_error:.3f} pixels"

    def test_triangulation_with_noise(
            self, synthetic_setup_with_noise: SyntheticCameraSetup, random_3d_points: np.ndarray
    ) -> None:
        """Test triangulation with realistic pixel noise."""
        triangulator = PointTriangulator(
            camera_calibrations=synthetic_setup_with_noise.camera_calibrations
        )

        points2d_by_camera = synthetic_setup_with_noise.project_points(random_3d_points)

        points2d = np.stack(
            [points2d_by_camera[cam_id] for cam_id in triangulator.camera_names], axis=1
        )

        triangulated_3d, errors = triangulator.triangulate_points(
            points2d=points2d, undistort_points=False, compute_reprojection_error=True
        )

        # With noise, accuracy will be worse but still reasonable
        max_error = np.max(np.linalg.norm(triangulated_3d - random_3d_points, axis=1))
        assert max_error < 0.1, f"Max reconstruction error with noise: {max_error:.6f}m"

        # Reprojection errors should reflect the added noise
        mean_reprojection_error = np.mean(errors)
        assert mean_reprojection_error > 0.3, "Reprojection error should reflect added noise"
        assert mean_reprojection_error < 2.0, f"Mean reprojection error too high: {mean_reprojection_error:.3f} pixels"

    def test_triangulate_dict_api_manual_debug(
            self, synthetic_setup_2_cameras: SyntheticCameraSetup
    ) -> None:
        """Manually debug the dict triangulation to isolate the issue."""
        triangulator = PointTriangulator(
            camera_calibrations=synthetic_setup_2_cameras.camera_calibrations
        )

        # Single test point - NOT at origin to avoid degenerate case
        test_point_3d = np.array([[0.1, 0.2, 1.0]])

        # Project using each camera
        points2d_list: list[np.ndarray] = []
        for cam_id in triangulator.camera_names:
            camera = triangulator.camera_calibrations[cam_id]
            point_2d = camera.project_3d_to_2d(test_point_3d)
            points2d_list.append(point_2d)
            print(f"Camera {cam_id} projects {test_point_3d[0]} to {point_2d[0]}")

        # Test array API
        points2d_array = np.stack(points2d_list, axis=1)
        print(f"\nArray API input shape: {points2d_array.shape}")
        print(f"Array API input:\n{points2d_array}")

        result_array, _ = triangulator.triangulate_points(points2d=points2d_array)
        print(f"Array API result: {result_array[0]}")
        print(f"Array API error: {np.linalg.norm(result_array[0] - test_point_3d[0]):.6f}m")

        # Now manually do what dict API does
        points2d_by_camera_dict: dict[str, dict[str, tuple[float, float]]] = {}
        for idx, cam_id in enumerate(triangulator.camera_names):
            points2d_by_camera_dict[cam_id] = {
                "test_point": (float(points2d_list[idx][0, 0]), float(points2d_list[idx][0, 1]))
            }

        print(f"\nDict API input: {points2d_by_camera_dict}")

        result_dict = triangulator.triangulate_dict(
            points2d_by_camera=points2d_by_camera_dict,
            min_cameras=2
        )

        print(f"Dict API result: {result_dict['test_point']}")

        reconstructed = np.array(result_dict['test_point'])
        assert not np.any(np.isnan(reconstructed)), f"Dict API returned NaN: {reconstructed}"

        error = np.linalg.norm(reconstructed - test_point_3d[0])
        assert error < 0.01, f"Dict API error: {error:.6f}m"

    def test_triangulate_dict_api(
            self, synthetic_setup_2_cameras: SyntheticCameraSetup
    ) -> None:
        """Test dictionary-based triangulation API."""
        triangulator = PointTriangulator(
            camera_calibrations=synthetic_setup_2_cameras.camera_calibrations
        )

        # Create test points with names - all in front of cameras (positive Z)
        test_points_3d: dict[str, np.ndarray] = {
            "point_A": np.array([0.0, 0.0, 2.0]),
            "point_B": np.array([0.3, 0.2, 3.0]),
            "point_C": np.array([-0.2, -0.1, 2.5]),
        }

        # First verify that the array-based API works with the same points
        points2d_by_camera_for_array: dict[str, np.ndarray] = {}
        for camera_id in triangulator.camera_names:
            camera = synthetic_setup_2_cameras.camera_calibrations[camera_id]
            points3d_array = np.array([test_points_3d[name] for name in test_points_3d.keys()])
            points2d_array = camera.project_3d_to_2d(points3d_array)
            points2d_by_camera_for_array[camera_id] = points2d_array

        # Stack for array API
        points2d_stacked = np.stack(
            [points2d_by_camera_for_array[cam_id] for cam_id in triangulator.camera_names],
            axis=1
        )

        # Verify array API works
        array_result, _ = triangulator.triangulate_points(points2d=points2d_stacked)
        assert not np.any(np.isnan(array_result)), "Array API should not return NaN"

        # Now test dict API with the same data
        # IMPORTANT: Maintain consistent point name order across all cameras
        point_names_ordered = list(test_points_3d.keys())
        points2d_by_camera: dict[str, dict[str, tuple[float, float]]] = {}

        for camera_id in triangulator.camera_names:
            points2d_by_camera[camera_id] = {}
            for idx, point_name in enumerate(point_names_ordered):
                point_2d = points2d_by_camera_for_array[camera_id][idx]
                points2d_by_camera[camera_id][point_name] = (float(point_2d[0]), float(point_2d[1]))

        # Triangulate using dict API
        results = triangulator.triangulate_dict(
            points2d_by_camera=points2d_by_camera,
            min_cameras=2,
            compute_reprojection_error=False,
        )

        # Verify results
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"

        for point_idx, (point_name, point_3d_original) in enumerate(test_points_3d.items()):
            assert point_name in results, f"Point {point_name} not in results"
            reconstructed = np.array(results[point_name])

            # Check that we got valid (non-NaN) results
            if np.any(np.isnan(reconstructed)):
                print(f"\nDEBUG INFO for {point_name}:")
                print(f"  Reconstructed (dict API): {reconstructed}")
                print(f"  Expected (array API):     {array_result[point_idx]}")
                print(f"  Original 3D:              {point_3d_original}")
                print(f"  2D observations:")
                for cam_id in triangulator.camera_names:
                    print(f"    {cam_id}: {points2d_by_camera[cam_id][point_name]}")
                print(f"  Camera names order: {triangulator.camera_names}")
                print(f"  Points2d dict keys: {list(points2d_by_camera.keys())}")

            assert not np.any(np.isnan(reconstructed)), (
                f"Point {point_name} returned NaN: {reconstructed}\n"
                f"Array API gave: {array_result[point_idx]}"
            )

            error = np.linalg.norm(reconstructed - point_3d_original)
            assert error < 0.01, f"Point {point_name} reconstruction error: {error:.6f}m"

    def test_triangulate_dict_with_reprojection_error(
            self, synthetic_setup_2_cameras: SyntheticCameraSetup
    ) -> None:
        """Test dict API with reprojection error computation."""
        triangulator = PointTriangulator(
            camera_calibrations=synthetic_setup_2_cameras.camera_calibrations
        )

        test_point_3d = np.array([0.1, -0.05, 2.5])

        points2d_by_camera: dict[str, dict[str, tuple[float, float]]] = {}
        for camera_id in triangulator.camera_names:
            camera = synthetic_setup_2_cameras.camera_calibrations[camera_id]
            point_2d = camera.project_3d_to_2d(test_point_3d.reshape(1, 3))[0]
            points2d_by_camera[camera_id] = {
                "test_point": (float(point_2d[0]), float(point_2d[1]))
            }

        results = triangulator.triangulate_dict(
            points2d_by_camera=points2d_by_camera,
            min_cameras=2,
            compute_reprojection_error=True,
        )

        assert "test_point" in results
        assert isinstance(results["test_point"], dict)
        assert "point" in results["test_point"]
        assert "error" in results["test_point"]

        reconstructed = np.array(results["test_point"]["point"])
        error_3d = np.linalg.norm(reconstructed - test_point_3d)
        assert error_3d < 0.01

        reprojection_error = results["test_point"]["error"]
        assert reprojection_error < 1.0

    def test_triangulate_dict_missing_observations(
            self, synthetic_setup_4_cameras: SyntheticCameraSetup
    ) -> None:
        """Test dict API when some cameras don't observe all points."""
        triangulator = PointTriangulator(
            camera_calibrations=synthetic_setup_4_cameras.camera_calibrations
        )

        test_point_3d = np.array([0.0, 0.0, 2.0])

        # Only 3 out of 4 cameras observe the point
        cameras_to_use = list(triangulator.camera_names)[:3]

        points2d_by_camera: dict[str, dict[str, tuple[float, float]]] = {}
        for camera_id in cameras_to_use:
            camera = synthetic_setup_4_cameras.camera_calibrations[camera_id]
            point_2d = camera.project_3d_to_2d(test_point_3d.reshape(1, 3))[0]
            points2d_by_camera[camera_id] = {
                "visible_point": (float(point_2d[0]), float(point_2d[1]))
            }

        results = triangulator.triangulate_dict(
            points2d_by_camera=points2d_by_camera, min_cameras=2
        )

        assert "visible_point" in results
        reconstructed = np.array(results["visible_point"])
        error = np.linalg.norm(reconstructed - test_point_3d)
        assert error < 0.01

    def test_triangulate_dict_insufficient_cameras(
            self, synthetic_setup_4_cameras: SyntheticCameraSetup
    ) -> None:
        """Test dict API when point is only visible in one camera (should return NaN)."""
        triangulator = PointTriangulator(
            camera_calibrations=synthetic_setup_4_cameras.camera_calibrations
        )

        test_point_3d = np.array([0.0, 0.0, 3.0])

        # Only 1 camera observes the point (insufficient)
        camera_id = triangulator.camera_names[0]
        camera = synthetic_setup_4_cameras.camera_calibrations[camera_id]
        point_2d = camera.project_3d_to_2d(test_point_3d.reshape(1, 3))[0]

        points2d_by_camera: dict[str, dict[str, tuple[float, float]]] = {
            camera_id: {"insufficient_point": (float(point_2d[0]), float(point_2d[1]))}
        }

        results = triangulator.triangulate_dict(
            points2d_by_camera=points2d_by_camera, min_cameras=2
        )

        assert "insufficient_point" in results
        result_tuple = results["insufficient_point"]
        assert all(np.isnan(result_tuple))

    def test_triangulation_validates_input_shape(
            self, synthetic_setup_2_cameras: SyntheticCameraSetup
    ) -> None:
        """Test that triangulation validates input array shapes."""
        triangulator = PointTriangulator(
            camera_calibrations=synthetic_setup_2_cameras.camera_calibrations
        )

        # Wrong number of cameras
        wrong_camera_count = np.random.rand(10, 3, 2)  # 3 cameras instead of 2
        with pytest.raises(ValueError, match="cameras but triangulator"):
            triangulator.triangulate_points(points2d=wrong_camera_count)

        # Wrong last dimension
        wrong_dim = np.random.rand(10, 2, 3)  # Last dim should be 2, not 3
        with pytest.raises(ValueError, match="must have shape"):
            triangulator.triangulate_points(points2d=wrong_dim)

    def test_undistort_points_returns_normalized_coordinates(
            self, synthetic_setup_2_cameras: SyntheticCameraSetup, random_3d_points: np.ndarray
    ) -> None:
        """
        Test that undistort_points flag works correctly.

        NOTE: When undistort_points=True, cv2.undistortPoints returns NORMALIZED
        camera coordinates (not pixel coordinates), so the triangulation results
        will differ from using pixel coordinates directly.
        """
        triangulator = PointTriangulator(
            camera_calibrations=synthetic_setup_2_cameras.camera_calibrations
        )

        points2d_by_camera = synthetic_setup_2_cameras.project_points(random_3d_points)
        points2d = np.stack(
            [points2d_by_camera[cam_id] for cam_id in triangulator.camera_names], axis=1
        )

        # Triangulate with pixel coordinates (standard approach)
        triangulated_no_undistort, _ = triangulator.triangulate_points(
            points2d=points2d, undistort_points=False
        )

        # Verify this gives accurate results
        max_error = np.max(np.linalg.norm(triangulated_no_undistort - random_3d_points, axis=1))
        assert max_error < 0.01, "Standard triangulation should be accurate"

        # The undistort_points flag changes coordinate system, so we just verify it runs
        # without errors (actual correctness depends on using appropriate projection matrices)
        triangulated_with_undistort, _ = triangulator.triangulate_points(
            points2d=points2d, undistort_points=True
        )

        # Just verify we got valid output
        assert triangulated_with_undistort.shape == random_3d_points.shape
        assert not np.any(np.isnan(triangulated_with_undistort))

    def test_reprojection_error_computation(
            self, synthetic_setup_2_cameras: SyntheticCameraSetup, random_3d_points: np.ndarray
    ) -> None:
        """Test that reprojection error computation is accurate."""
        triangulator = PointTriangulator(
            camera_calibrations=synthetic_setup_2_cameras.camera_calibrations
        )

        points2d_by_camera = synthetic_setup_2_cameras.project_points(random_3d_points)
        points2d = np.stack(
            [points2d_by_camera[cam_id] for cam_id in triangulator.camera_names], axis=1
        )

        triangulated_3d, errors = triangulator.triangulate_points(
            points2d=points2d, compute_reprojection_error=True
        )

        # Manually compute reprojection for first point to verify
        point_3d = triangulated_3d[0]
        manual_errors: list[float] = []

        for camera_id, camera in triangulator.camera_calibrations.items():
            projected = camera.project_3d_to_2d(point_3d.reshape(1, 3))[0]
            cam_idx = triangulator.camera_names.index(camera_id)
            original = points2d[0, cam_idx]
            error = np.linalg.norm(projected - original)
            manual_errors.append(error)

        manual_mean_error = np.mean(manual_errors)

        # Should match computed error for first point
        assert np.abs(errors[0] - manual_mean_error) < 0.01

    def test_empty_triangulator_raises_error(self) -> None:
        """Test that creating triangulator with no cameras raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            PointTriangulator(camera_calibrations={})

    def test_camera_calibration_data_world_coordinates(
            self, synthetic_setup_2_cameras: SyntheticCameraSetup
    ) -> None:
        """Test that world_position and world_orientation are computed correctly."""
        camera = list(synthetic_setup_2_cameras.camera_calibrations.values())[0]

        # World position should be non-zero (camera is not at origin)
        assert np.linalg.norm(camera.world_position) > 0.1

        # World orientation should be orthonormal
        assert np.allclose(
            camera.world_orientation @ camera.world_orientation.T, np.eye(3), atol=1e-6
        )

    def test_projection_and_unprojection_consistency(
            self, synthetic_setup_2_cameras: SyntheticCameraSetup
    ) -> None:
        """Test that project_3d_to_2d and triangulation are consistent."""
        triangulator = PointTriangulator(
            camera_calibrations=synthetic_setup_2_cameras.camera_calibrations
        )

        # Single test point in front of cameras
        original_3d = np.array([[0.05, 0.1, 2.0]])

        # Project to 2D
        points2d_list: list[np.ndarray] = []
        for camera in triangulator.camera_calibrations.values():
            point_2d = camera.project_3d_to_2d(original_3d)
            points2d_list.append(point_2d)

        points2d = np.stack(points2d_list, axis=1)

        # Triangulate back
        reconstructed_3d, _ = triangulator.triangulate_points(points2d=points2d)

        # Should match original
        error = np.linalg.norm(reconstructed_3d[0] - original_3d[0])
        assert error < 0.001, f"Round-trip error: {error:.6f}m"


class TestCameraCalibrationData:
    """Test suite for CameraCalibrationData class."""

    def test_from_dict_with_image_size_key(self) -> None:
        """Test loading from dict with 'image_size' key."""
        data = {
            "image_size": [1920, 1080],
            "matrix": {"matrix": [[1000.0, 0.0, 960.0], [0.0, 1000.0, 540.0], [0.0, 0.0, 1.0]]},
            "distortions": {"coefficients": [0.0, 0.0, 0.0, 0.0, 0.0]},
            "rotation": [0.0, 0.0, 0.0],
            "translation": [0.0, 0.0, 0.0],
        }

        camera = CameraCalibrationData.from_dict(camera_id="test_cam", data=data)

        assert camera.name == "test_cam"
        assert camera.image_size == (1920, 1080)

    def test_from_dict_with_size_key(self) -> None:
        """Test loading from dict with 'size' key (legacy)."""
        data = {
            "size": [1280, 720],
            "matrix": {"matrix": [[800.0, 0.0, 640.0], [0.0, 800.0, 360.0], [0.0, 0.0, 1.0]]},
            "distortions": {"coefficients": [0.0, 0.0, 0.0, 0.0, 0.0]},
            "rotation": [0.0, 0.0, 0.0],
            "translation": [0.0, 0.0, 0.0],
        }

        camera = CameraCalibrationData.from_dict(camera_id="legacy_cam", data=data)

        assert camera.image_size == (1280, 720)

    def test_from_dict_missing_size_raises_error(self) -> None:
        """Test that missing size key raises error."""
        data = {
            "matrix": {"matrix": [[1000.0, 0.0, 960.0], [0.0, 1000.0, 540.0], [0.0, 0.0, 1.0]]},
            "distortions": {"coefficients": [0.0, 0.0, 0.0, 0.0, 0.0]},
            "rotation": [0.0, 0.0, 0.0],
            "translation": [0.0, 0.0, 0.0],
        }

        with pytest.raises(KeyError, match="image_size"):
            CameraCalibrationData.from_dict(camera_id="bad_cam", data=data)

    def test_projection_matrix_shape(
            self, synthetic_setup_2_cameras: SyntheticCameraSetup
    ) -> None:
        """Test that projection matrix has correct shape."""
        camera = list(synthetic_setup_2_cameras.camera_calibrations.values())[0]

        assert camera.projection_matrix.shape == (3, 4)
        assert camera.extrinsics_matrix.shape == (3, 4)

    def test_undistort_points_shape_preservation(
            self, synthetic_setup_2_cameras: SyntheticCameraSetup
    ) -> None:
        """Test that undistort_points preserves input shape."""
        camera = list(synthetic_setup_2_cameras.camera_calibrations.values())[0]

        # Test with different input shapes
        points_2d_flat = np.random.rand(10, 2) * 1000
        points_2d_opencv = np.random.rand(10, 1, 2) * 1000

        undistorted_flat = camera.undistort_points(points_2d_flat)
        undistorted_opencv = camera.undistort_points(points_2d_opencv)

        assert undistorted_flat.shape == (10, 2)
        assert undistorted_opencv.shape == (10, 1, 2)

if __name__ == "__main__":
    pytest.main([__file__])