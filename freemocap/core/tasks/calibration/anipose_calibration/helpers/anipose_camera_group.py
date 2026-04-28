import multiprocessing.synchronize
from typing import Any

import cv2
import numpy as np
from numba import jit
from pydantic import BaseModel, ConfigDict, Field
from scipy import optimize
from scipy.sparse import dok_matrix
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.tasks.calibration.anipose_calibration.helpers.anipose_camera import AniposeCamera
from freemocap.core.tasks.calibration.anipose_calibration.helpers.freemocap_anipose import (
    BoardObservations,
    OptionalBoardObservations,
    get_connections,
    get_error_dict,
    get_initial_extrinsics,
    extract_roration_translation_vectors,
    extract_points,
    merge_rows,
    resample_points,
    subset_extra,
    remap_ids,
    transform_points,
    logger,
)
from freemocap.core.tasks.calibration.shared.transform_math import make_M, get_rtvec


class AniposeCameraGroup(BaseModel):
    """Group of calibrated cameras supporting triangulation and bundle adjustment."""

    model_config = ConfigDict(arbitrary_types_allowed=True,
                              extra="forbid",
                              populate_by_name=True)

    cameras: list[AniposeCamera] = Field(
        description="Ordered list of cameras in this group",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary calibration metadata",
    )

    # -----------------------------------------------------------------
    # PROPERTIES
    # -----------------------------------------------------------------

    @property
    def camera_ids(self) -> list[CameraIdString]:
        """Ordered list of camera ID strings."""
        return [CameraIdString(cam.id) for cam in self.cameras]

    @property
    def rotations(self) -> np.ndarray:
        """(num_cameras, 3) Rodrigues rotation vectors, one per camera."""
        return np.array([cam.rotation_vector for cam in self.cameras])

    @rotations.setter
    def rotations(self, rvecs: np.ndarray) -> None:
        for cam, rvec in zip(self.cameras, rvecs):
            cam.rotation_vector = rvec

    @property
    def translations(self) -> np.ndarray:
        """(num_cameras, 3) translation vectors, one per camera."""
        return np.array([cam.translation_vector for cam in self.cameras])

    @translations.setter
    def translations(self, tvecs: np.ndarray) -> None:
        for cam, tvec in zip(self.cameras, tvecs):
            cam.translation_vector = tvec

    @property
    def world_positions(self) -> np.ndarray:
        """(num_cameras, 3) world-frame positions, one per camera."""
        return np.stack([cam.world_position for cam in self.cameras])

    @world_positions.setter
    def world_positions(self, positions: np.ndarray) -> None:
        for cam, position in zip(self.cameras, positions):
            cam.world_position = position

    @property
    def world_orientations(self) -> np.ndarray:
        """(num_cameras, 3, 3) world-frame orientation matrices, one per camera."""
        return np.stack([cam.world_orientation for cam in self.cameras])

    @world_orientations.setter
    def world_orientations(self, orientations: np.ndarray) -> None:
        for cam, orientation in zip(self.cameras, orientations):
            cam.world_orientation = orientation

    # -----------------------------------------------------------------
    # TRIANGULATION
    # -----------------------------------------------------------------

    def _to_triangulator(self):
        """Build a Triangulator from the current (in-flight) AniposeCamera state.

        Solver iterations mutate camera intrinsics/extrinsics, so this rebuilds
        on every call. Pydantic construction cost is microseconds; solver
        iterations take seconds.
        """
        from freemocap.core.tasks.calibration.shared.calibration_models import CameraModel
        from freemocap.core.tasks.triangulation.triangulator import Triangulator
        return Triangulator(
            cameras=[CameraModel.from_anipose_camera(cam) for cam in self.cameras],
        )

    def triangulate(
        self,
        points: np.ndarray,
        undistort: bool = True,
        progress: bool = False,
        kill_event: multiprocessing.synchronize.Event | None = None,
    ) -> np.ndarray | None:
        """Triangulate a (num_cameras, N, 2) image-point array to (N, 3) world points.

        Args:
            points: (num_cameras, N, 2) observed image coordinates; NaN where unobserved.
            undistort: Apply lens distortion correction before triangulation.
            progress: Unused; kept for API compatibility.
            kill_event: If set, returns ``None`` immediately (cooperative cancellation).

        Returns:
            (N, 3) array of triangulated world points, or ``None`` if cancelled.
        """
        from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig

        assert points.shape[0] == len(self.cameras), (
            f"First dim should equal number of cameras ({len(self.cameras)}), "
            f"but shape is {points.shape}"
        )

        one_point = False
        if len(points.shape) == 2:
            points = points.reshape(-1, 1, 2)
            one_point = True

        if kill_event is not None and kill_event.is_set():
            return None

        triangulator = self._to_triangulator()
        result = triangulator.triangulate(
            data2d=points,
            config=TriangulationConfig(use_outlier_rejection=False),
            assume_undistorted_normalized=not undistort,
        )
        out = result.points_3d

        if one_point:
            out = out[0]
        return out

    def reprojection_error(
        self,
        points_3d: np.ndarray,
        points_2d: np.ndarray,
        mean: bool = False,
    ) -> np.ndarray | float:
        """Compute reprojection error between 3-D points and 2-D observations.

        Args:
            points_3d: (N, 3) world-space points.
            points_2d: (num_cameras, N, 2) observed image coordinates.
            mean: If True, return per-point mean error magnitude (shape N);
                  if False, return signed (num_cameras, N, 2) residuals.

        Returns:
            (N,) mean errors when ``mean=True``, else (num_cameras, N, 2) residuals.
        """
        one_point = False
        if len(points_3d.shape) == 1 and len(points_2d.shape) == 2:
            points_3d = points_3d.reshape(1, 3)
            points_2d = points_2d.reshape(-1, 1, 2)
            one_point = True

        num_cameras, num_points, _ = points_2d.shape
        assert points_3d.shape == (num_points, 3), (
            f"2D/3D shape mismatch: 2D={points_2d.shape}, 3D={points_3d.shape}"
        )

        triangulator = self._to_triangulator()
        if mean:
            errors = triangulator.mean_reprojection_error(
                points_3d=points_3d, points_2d_pixel=points_2d,
            )
        else:
            errors = triangulator.signed_reprojection_error(
                points_3d=points_3d, points_2d_pixel=points_2d,
            )

        if one_point:
            errors = float(errors[0]) if mean else errors.reshape(-1, 2)
        return errors

    # -----------------------------------------------------------------
    # BUNDLE ADJUSTMENT
    # -----------------------------------------------------------------

    def bundle_adjust_iter(
            self,
            points_2d: np.ndarray,
            board_observations: OptionalBoardObservations = None,
            num_iterations: int = 10,
            damping_start: float = 15,
            damping_end: float = 1,
            max_nfev: int = 200,
            ftol: float = 1e-4,
            num_samples_per_iteration: int = 100,
            num_samples_full: int = 1000,
            error_threshold: float = 0.3,
            verbose: bool = True,
    ) -> float:
        """Iterative bundle adjustment with a decaying outlier-rejection schedule.

        Runs ``num_iterations`` rounds of bundle adjustment on subsampled points.
        The reprojection-error threshold (``mu``) decays from ``damping_start``
        to ``damping_end`` to progressively exclude outliers.

        Args:
            points_2d: (num_cameras, N, 2) observed image coordinates.
            board_observations: Optional charuco board metadata for object-point constraints.
            num_iterations: Number of outer damping iterations.
            damping_start: Initial outlier threshold (pixels).
            damping_end: Final outlier threshold (pixels).
            max_nfev: Maximum function evaluations per inner optimisation call.
            ftol: Function tolerance for inner optimisation.
            num_samples_per_iteration: Points to use in each inner bundle adjust call.
            num_samples_full: Points to draw from when computing error statistics.
            error_threshold: Stop early if median error drops below this (pixels).
            verbose: Print progress each iteration.

        Returns:
            Final median reprojection error (pixels).
        """
        assert points_2d.shape[0] == len(self.cameras), (
            f"First dim should equal number of cameras ({len(self.cameras)}), "
            f"but shape is {points_2d.shape}"
        )

        points_2d_full = points_2d
        board_observations_full = board_observations

        points_2d, board_observations = resample_points(
            points_2d_full, board_observations_full, num_samples=num_samples_full
        )
        error = self.average_error(points_2d, median=True)

        if verbose:
            print("error: ", error)

        mus = np.exp(np.linspace(np.log(damping_start), np.log(damping_end), num=num_iterations))

        for iteration in range(num_iterations):
            points_2d, board_observations = resample_points(
                points_2d_full, board_observations_full, num_samples=num_samples_full
            )
            points_3d = self.triangulate(points_2d)
            errors_full = self.reprojection_error(points_3d, points_2d, mean=False)
            errors_norm = self.reprojection_error(points_3d, points_2d, mean=True)

            error_dict = get_error_dict(errors_full)
            max_error = 0
            min_error = 0
            for k, v in error_dict.items():
                num, percents = v
                max_error = max(percents[-1], max_error)
                min_error = max(percents[0], min_error)
            mu = max(min(max_error, mus[iteration]), min_error)

            good = errors_norm < mu
            board_observations_good = subset_extra(board_observations, good)
            points_2d_samp, board_observations_samp = resample_points(
                points_2d[:, good], board_observations_good, num_samples=num_samples_per_iteration
            )

            error = np.median(errors_norm)

            if error < error_threshold:
                break

            if verbose:
                print(error_dict)
                print("error: {:.2f}, mu: {:.1f}, ratio: {:.3f}".format(error, mu, np.mean(good)))

            self.bundle_adjust(
                points_2d_samp,
                board_observations_samp,
                loss="linear",
                ftol=ftol,
                max_nfev=max_nfev,
                verbose=verbose,
            )

        # Final pass with relaxed threshold
        points_2d, board_observations = resample_points(
            points_2d_full, board_observations_full, num_samples=num_samples_full
        )
        points_3d = self.triangulate(points_2d)
        errors_full = self.reprojection_error(points_3d, points_2d, mean=False)
        errors_norm = self.reprojection_error(points_3d, points_2d, mean=True)
        error_dict = get_error_dict(errors_full)

        max_error = 0
        min_error = 0
        for k, v in error_dict.items():
            num, percents = v
            max_error = max(percents[-1], max_error)
            min_error = max(percents[0], min_error)
        mu = max(max(max_error, damping_end), min_error)

        good = errors_norm < mu
        board_observations_good = subset_extra(board_observations, good)
        self.bundle_adjust(
            points_2d[:, good],
            board_observations_good,
            loss="linear",
            ftol=ftol,
            max_nfev=max(200, max_nfev),
            verbose=verbose,
        )

        return self.average_error(points_2d, median=True)

    def bundle_adjust(
            self,
            points_2d: np.ndarray,
            board_observations: OptionalBoardObservations = None,
            loss: str = "linear",
            threshold: float = 50,
            ftol: float = 1e-4,
            max_nfev: int = 1000,
            start_params: np.ndarray | None = None,
            verbose: bool = True,
    ) -> float:
        """Fine-tune camera parameters via scipy least_squares bundle adjustment.

        Args:
            points_2d: (num_cameras, N, 2) observed image coordinates.
            board_observations: Optional charuco board metadata for object-point constraints.
            loss: Loss function name passed to ``scipy.optimize.least_squares``.
            threshold: Soft L1 / Huber threshold (``f_scale`` in scipy).
            ftol: Function tolerance for convergence.
            max_nfev: Maximum function evaluations.
            start_params: If provided, override the default parameter initialisation.
            verbose: Print scipy solver progress.

        Returns:
            Mean reprojection error (pixels) after optimisation.
        """
        assert points_2d.shape[0] == len(self.cameras), (
            f"First dim should equal number of cameras ({len(self.cameras)}), "
            f"but shape is {points_2d.shape}"
        )

        if board_observations is not None:
            board_observations["ids_map"] = remap_ids(board_observations["ids"])

        x0, num_camera_params = self._initialize_params_bundle(points_2d, board_observations)

        if start_params is not None:
            x0 = start_params
            num_camera_params = len(self.cameras[0].get_params())

        jac_sparse = self._jac_sparsity_bundle(points_2d, num_camera_params, board_observations)

        opt = optimize.least_squares(
            self._error_fun_bundle,
            x0,
            jac_sparsity=jac_sparse,
            f_scale=threshold,
            x_scale="jac",
            loss=loss,
            ftol=ftol,
            method="trf",
            tr_solver="lsmr",
            verbose=2 * verbose,
            max_nfev=max_nfev,
            args=(points_2d, num_camera_params, board_observations),
        )

        for camera_index, cam in enumerate(self.cameras):
            param_start = camera_index * num_camera_params
            param_end = (camera_index + 1) * num_camera_params
            cam.set_params(opt.x[param_start:param_end])

        return self.average_error(points_2d)

    @jit(parallel=True, forceobj=True)
    def _error_fun_bundle(
            self,
            params: np.ndarray,
            points_2d: np.ndarray,
            num_camera_params: int,
            board_observations: OptionalBoardObservations,
    ) -> np.ndarray:
        """Residual function for bundle adjustment (called by scipy least_squares).

        Args:
            params: Flat parameter vector [camera_params... | 3d_points... | board_poses...].
            points_2d: (num_cameras, N, 2) observed image coordinates.
            num_camera_params: Number of parameters per camera.
            board_observations: Board metadata for object-point constraints.

        Returns:
            1-D residual vector of reprojection errors and (optionally) board constraints.
        """
        good = ~np.isnan(points_2d)
        num_cameras = len(self.cameras)

        for camera_index in range(num_cameras):
            param_start = camera_index * num_camera_params
            param_end = (camera_index + 1) * num_camera_params
            self.cameras[camera_index].set_params(params[param_start:param_end])

        total_cam_params = num_camera_params * num_cameras
        num_3d_params = points_2d.shape[1] * 3
        points_3d_test = params[total_cam_params: total_cam_params + num_3d_params].reshape(-1, 3)
        errors_reproj = self.reprojection_error(points_3d_test, points_2d)[good]

        if board_observations is not None:
            ids = board_observations["ids_map"]
            objp = board_observations["objp"]
            min_scale = np.min(objp[objp > 0])
            num_boards = int(np.max(ids)) + 1
            board_param_start = total_cam_params + num_3d_params
            rvecs = params[board_param_start: board_param_start + num_boards * 3].reshape(-1, 3)
            tvecs = params[board_param_start + num_boards * 3: board_param_start + num_boards * 6].reshape(-1, 3)
            expected = transform_points(objp, rvecs[ids], tvecs[ids])
            errors_obj = 2 * (points_3d_test - expected).ravel() / min_scale
        else:
            errors_obj = np.array([])

        return np.hstack([errors_reproj, errors_obj])

    def _jac_sparsity_bundle(
            self,
            points_2d: np.ndarray,
            num_camera_params: int,
            board_observations: OptionalBoardObservations,
    ) -> dok_matrix:
        """Compute the sparsity structure of the Jacobian for bundle adjustment.

        Args:
            points_2d: (num_cameras, N, 2) observed image coordinates.
            num_camera_params: Number of parameters per camera.
            board_observations: Board metadata; required to account for board pose params.

        Returns:
            Sparse (num_errors, num_params) matrix marking non-zero Jacobian entries.
        """
        point_indices = np.zeros(points_2d.shape, dtype="int32")
        cam_indices = np.zeros(points_2d.shape, dtype="int32")

        for point_index in range(points_2d.shape[1]):
            point_indices[:, point_index] = point_index
        for camera_index in range(points_2d.shape[0]):
            cam_indices[camera_index] = camera_index

        good = ~np.isnan(points_2d)

        if board_observations is not None:
            ids = board_observations["ids_map"]
            num_boards = int(np.max(ids)) + 1
            total_board_params = num_boards * 6
        else:
            num_boards = 0
            total_board_params = 0

        num_cameras = points_2d.shape[0]
        num_points = points_2d.shape[1]
        total_params_reproj = num_cameras * num_camera_params + num_points * 3
        num_params = total_params_reproj + total_board_params

        num_good_values = np.sum(good)
        num_errors = num_good_values + (num_points * 3 if board_observations is not None else 0)

        A_sparse = dok_matrix((num_errors, num_params), dtype="int16")

        cam_indices_good = cam_indices[good]
        point_indices_good = point_indices[good]
        ix = np.arange(num_good_values)

        for param_offset in range(num_camera_params):
            A_sparse[ix, cam_indices_good * num_camera_params + param_offset] = 1
        for coord in range(3):
            A_sparse[ix, num_cameras * num_camera_params + point_indices_good * 3 + coord] = 1

        if board_observations is not None:
            point_ix = np.arange(num_points)
            for i in range(3):
                for j in range(3):
                    A_sparse[num_good_values + point_ix * 3 + i, total_params_reproj + ids * 3 + j] = 1
                    A_sparse[
                        num_good_values + point_ix * 3 + i,
                        total_params_reproj + num_boards * 3 + ids * 3 + j,
                    ] = 1
            for i in range(3):
                A_sparse[
                    num_good_values + point_ix * 3 + i,
                    num_cameras * num_camera_params + point_ix * 3 + i,
                ] = 1

        return A_sparse

    def _initialize_params_bundle(
            self,
            points_2d: np.ndarray,
            board_observations: OptionalBoardObservations,
    ) -> tuple[np.ndarray, int]:
        """Build the initial parameter vector for bundle adjustment.

        Layout: [camera_params... | 3d_points... | board_rvecs... | board_tvecs...]

        Args:
            points_2d: (num_cameras, N, 2) observed image coordinates.
            board_observations: Board metadata including ``ids_map``, ``rvecs``, ``tvecs``.

        Returns:
            Tuple of (x0 parameter vector, num_camera_params per camera).
        """
        cam_params = np.hstack([cam.get_params() for cam in self.cameras])
        num_camera_params = len(cam_params) // len(self.cameras)
        total_cam_params = len(cam_params)

        num_cameras, num_points, _ = points_2d.shape
        assert num_cameras == len(self.cameras), "Camera count mismatch between group and 2D points"

        points_3d = self.triangulate(points_2d)

        if board_observations is not None:
            ids = board_observations["ids_map"]
            num_boards = int(np.max(ids[~np.isnan(ids)])) + 1
            total_board_params = num_boards * 6

            rvecs = np.zeros((num_boards, 3), dtype="float64")
            tvecs = np.zeros((num_boards, 3), dtype="float64")

            if "rvecs" in board_observations and "tvecs" in board_observations:
                rvecs_all = board_observations["rvecs"]
                tvecs_all = board_observations["tvecs"]
                for board_num in range(num_boards):
                    point_id = np.where(ids == board_num)[0][0]
                    cam_ids_possible = np.where(~np.isnan(points_2d[:, point_id, 0]))[0]
                    cam_id = np.random.choice(cam_ids_possible)
                    M_cam = self.cameras[cam_id].extrinsics_matrix
                    M_board_cam = make_M(rvecs_all[cam_id, point_id], tvecs_all[cam_id, point_id])
                    M_board = np.linalg.inv(M_cam) @ M_board_cam
                    rvec, tvec = get_rtvec(M_board)
                    rvecs[board_num] = rvec
                    tvecs[board_num] = tvec
        else:
            total_board_params = 0

        x0 = np.zeros(total_cam_params + points_3d.size + total_board_params)
        x0[:total_cam_params] = cam_params
        x0[total_cam_params: total_cam_params + points_3d.size] = points_3d.ravel()

        if board_observations is not None:
            board_start = total_cam_params + points_3d.size
            x0[board_start: board_start + num_boards * 3] = rvecs.ravel()
            x0[board_start + num_boards * 3: board_start + num_boards * 6] = tvecs.ravel()

        return x0, num_camera_params

    # -----------------------------------------------------------------
    # AVERAGE ERROR
    # -----------------------------------------------------------------

    def average_error(self, points_2d: np.ndarray, median: bool = False) -> float:
        """Compute the average (or median) reprojection error across all observations.

        Args:
            points_2d: (num_cameras, N, 2) observed image coordinates.
            median: If True, return median error; otherwise mean.

        Returns:
            Scalar reprojection error in pixels.
        """
        points_3d = self.triangulate(points_2d)
        errors = self.reprojection_error(points_3d, points_2d, mean=True)
        return np.median(errors) if median else np.mean(errors)

    # -----------------------------------------------------------------
    # CALIBRATION
    # -----------------------------------------------------------------

    def calibrate_rows(
            self,
            all_rows: list[list[dict]],
            board,
            init_intrinsics: bool = True,
            init_extrinsics: bool = True,
            verbose: bool = True,
    ) -> tuple[float, list, list]:
        """Calibrate cameras from charuco board observation rows.

        Args:
            all_rows: One list of detection dicts per camera. Each dict must
                have ``framenum``, ``corners``, ``ids``, ``filled``.
            board: Calibration board object (``AniposeCharucoBoard``).
            init_intrinsics: Estimate camera matrices from point correspondences.
            init_extrinsics: Estimate initial camera poses from board observations.
            verbose: Log progress and connection statistics.

        Returns:
            Tuple of (reprojection_error, merged_rows, charuco_frame_numbers).
        """
        num_cameras = len(self.cameras)
        assert len(all_rows) == num_cameras, (
            f"Detection count ({len(all_rows)}) != camera count ({num_cameras})"
        )

        logger.info(f"Calibrating {num_cameras} cameras")
        for cam_idx, (rows, camera) in enumerate(zip(all_rows, self.cameras)):
            logger.info(f"Camera {cam_idx} ({camera.id}): {len(rows)} frames with detections")
            assert camera.size is not None, f"Camera '{camera.id}' has no frame size"

        if init_intrinsics:
            logger.info("Initializing camera intrinsics...")
            for cam_idx, (rows, camera) in enumerate(zip(all_rows, self.cameras)):
                objp, imgp = board.get_all_calibration_points(rows)
                mixed = [(o, i) for (o, i) in zip(objp, imgp) if len(o) >= 7]
                if len(mixed) == 0:
                    raise ValueError(f"No valid calibration points for camera {cam_idx} (need >= 7)")
                logger.info(f"  Camera {cam_idx}: {len(mixed)} usable frames")
                objp, imgp = zip(*mixed)
                matrix = cv2.initCameraMatrix2D(objp, imgp, tuple(camera.size))
                camera.camera_matrix = matrix

        logger.info("Estimating board poses...")
        for i, (row, cam) in enumerate(zip(all_rows, self.cameras)):
            all_rows[i] = board.estimate_pose_rows(cam, row)

        # solvePnP needs >= 6 charuco corners per frame; if a camera never saw
        # that many, calibration cannot proceed.
        for cam_idx, (rows, camera) in enumerate(zip(all_rows, self.cameras)):
            valid_poses = sum(1 for r in rows if r.get("rvec") is not None and r.get("tvec") is not None)
            if valid_poses == 0:
                raise ValueError(
                    f"Camera {cam_idx} ({camera.id}) has no frames with enough charuco corners "
                    f"for pose estimation (need >= 6 per frame). "
                    f"Ensure the charuco board is clearly visible and well-lit in every camera's view, "
                    f"and that the correct board dimensions are configured."
                )
            logger.info(f"  Camera {cam_idx} ({camera.id}): {valid_poses}/{len(rows)} frames have valid board pose")

        charuco_frames = [f["framenum"][1] for f in all_rows[0]]

        logger.info("Merging observations across cameras...")
        merged = merge_rows(all_rows=all_rows, camera_ids=self.camera_ids)

        image_points, board_observations = extract_points(merged, board, min_cameras=2)
        logger.info(f"Extracted points: shape={image_points.shape}")

        if init_extrinsics:
            logger.info("Initializing camera extrinsics...")
            rtvecs = extract_roration_translation_vectors(merged)

            if verbose:
                connections = get_connections(rtvecs, self.camera_ids)
                for (cam_a, cam_b), count in sorted(connections.items()):
                    if cam_a < cam_b:
                        logger.info(f"  {cam_a} <-> {cam_b}: {count} shared frames")

            rvecs, tvecs = get_initial_extrinsics(rtvecs, camera_ids=self.camera_ids)
            self.rotations = rvecs
            self.translations = tvecs

        logger.info("Starting iterative bundle adjustment...")
        error = self.bundle_adjust_iter(image_points, board_observations, verbose=verbose, error_threshold=1.0)
        logger.info(f"Calibration complete — final error: {error:.4f}")

        return error, merged, charuco_frames
