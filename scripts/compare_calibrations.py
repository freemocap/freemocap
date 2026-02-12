"""Compare calibration results and assess calibration health.

Provides:
  - Per-calibration health report (board reconstruction accuracy, per-camera stats)
  - Side-by-side comparison of two CalibrationResult objects
"""

import logging

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict

from freemocap.core.calibration.shared.calibration_models import CharucoBoardDefinition, CameraModel, \
    CharucoCornersObservation, CalibrationResult

logger = logging.getLogger(__name__)


# =============================================================================
# TRIANGULATION (shared utility)
# =============================================================================


def _triangulate_point_dlt(
    pixel_observations: list[tuple[NDArray[np.float64], NDArray[np.float64]]],
) -> NDArray[np.float64] | None:
    """Triangulate a single 3D point from 2D observations via DLT.

    Args:
        pixel_observations: List of (pixel_xy, projection_matrix_3x4) tuples.

    Returns:
        (3,) 3D point, or None if degenerate.
    """
    n_views = len(pixel_observations)
    if n_views < 2:
        return None

    A = np.zeros((n_views * 2, 4), dtype=np.float64)
    for vi, (px, P) in enumerate(pixel_observations):
        x, y = px
        A[vi * 2] = x * P[2] - P[0]
        A[vi * 2 + 1] = y * P[2] - P[1]

    _, _, vh = np.linalg.svd(A, full_matrices=False)
    pt_h = vh[-1]
    if abs(pt_h[3]) < 1e-10:
        return None
    return pt_h[:3] / pt_h[3]


# =============================================================================
# BOARD RECONSTRUCTION
# =============================================================================


def _get_adjacent_corner_pairs(
    board: CharucoBoardDefinition,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Get horizontal and vertical adjacent corner index pairs.

    Returns:
        (horizontal_pairs, vertical_pairs) — each a list of (idx_a, idx_b).
        Expected distance for each pair is board.square_length_mm.
    """
    cols = board.squares_x - 1
    rows = board.squares_y - 1

    horizontal: list[tuple[int, int]] = []
    vertical: list[tuple[int, int]] = []

    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            if c < cols - 1:
                horizontal.append((idx, idx + 1))
            if r < rows - 1:
                vertical.append((idx, idx + cols))

    return horizontal, vertical


def _triangulate_board_frame(
    *,
    cameras: list[CameraModel],
    frame_observations: dict[str, CharucoCornersObservation],
    n_corners: int,
) -> NDArray[np.float64]:
    """Triangulate all board corners for a single frame.

    Returns:
        (n_corners, 3) array with NaN for corners that couldn't be triangulated.
    """
    cam_by_name = {cam.name: cam for cam in cameras}
    result = np.full((n_corners, 3), np.nan, dtype=np.float64)

    for corner_id in range(n_corners):
        observations: list[tuple[NDArray[np.float64], NDArray[np.float64]]] = []

        for cam_name, obs in frame_observations.items():
            cam = cam_by_name.get(cam_name)
            if cam is None:
                continue
            for c in obs.corners:
                if c.corner_id == corner_id:
                    observations.append((c.pixel_xy, cam.projection_matrix))
                    break

        pt = _triangulate_point_dlt(observations)
        if pt is not None:
            result[corner_id] = pt

    return result


def _compute_board_distance_errors(
    *,
    cameras: list[CameraModel],
    board: CharucoBoardDefinition,
    all_observations: list[CharucoCornersObservation],
) -> NDArray[np.float64]:
    """Compute per-pair distance errors across all frames.

    For each frame, triangulates board corners and measures distances
    between adjacent corners. Returns the signed errors (measured - expected)
    for all valid pairs across all frames.
    """
    horizontal_pairs, vertical_pairs = _get_adjacent_corner_pairs(board=board)
    all_pairs = horizontal_pairs + vertical_pairs
    expected_distance = board.square_length_mm

    # Group observations by frame
    frame_groups: dict[int, dict[str, CharucoCornersObservation]] = {}
    for obs in all_observations:
        if obs.frame_index not in frame_groups:
            frame_groups[obs.frame_index] = {}
        frame_groups[obs.frame_index][obs.camera_name] = obs

    all_errors: list[float] = []

    for frame_idx in sorted(frame_groups.keys()):
        corners_3d = _triangulate_board_frame(
            cameras=cameras,
            frame_observations=frame_groups[frame_idx],
            n_corners=board.n_corners,
        )

        for idx_a, idx_b in all_pairs:
            pt_a = corners_3d[idx_a]
            pt_b = corners_3d[idx_b]
            if np.isnan(pt_a).any() or np.isnan(pt_b).any():
                continue
            measured = float(np.linalg.norm(pt_b - pt_a))
            all_errors.append(measured - expected_distance)

    return np.array(all_errors, dtype=np.float64)


# =============================================================================
# CALIBRATION HEALTH REPORT
# =============================================================================


class PerCameraHealth(BaseModel):
    """Health metrics for a single camera."""

    model_config = ConfigDict(extra="forbid")

    camera_name: str
    fx: float
    fy: float
    cx: float
    cy: float
    k1: float
    k2: float
    image_width: int
    image_height: int

    # Derived sanity checks
    focal_length_reasonable: bool
    principal_point_reasonable: bool
    fx_fy_ratio: float

    @property
    def summary(self) -> str:
        fl_flag = "✓" if self.focal_length_reasonable else "✗"
        pp_flag = "✓" if self.principal_point_reasonable else "✗"
        return (
            f"  {self.camera_name}:\n"
            f"    Focal length:    fx={self.fx:.1f}  fy={self.fy:.1f}  "
            f"(fx/fy={self.fx_fy_ratio:.3f})  [{fl_flag}]\n"
            f"    Principal point: cx={self.cx:.1f}  cy={self.cy:.1f}  "
            f"(image: {self.image_width}x{self.image_height})  [{pp_flag}]\n"
            f"    Distortion:      k1={self.k1:.4f}  k2={self.k2:.4f}"
        )


class BoardReconstructionHealth(BaseModel):
    """Board reconstruction accuracy — the ground-truth calibration quality metric.

    Triangulates charuco corners from the calibration and measures how
    well the inter-corner distances match the known board geometry.
    """

    model_config = ConfigDict(extra="forbid")

    n_distance_measurements: int
    expected_distance_mm: float

    # Signed errors (measured - expected) in mm
    mean_error_mm: float
    median_error_mm: float
    std_error_mm: float

    # Absolute errors in mm
    mean_abs_error_mm: float
    median_abs_error_mm: float
    max_abs_error_mm: float
    pct_within_1mm: float
    pct_within_5mm: float

    @property
    def summary(self) -> str:
        return (
            f"  Board reconstruction ({self.n_distance_measurements} adjacent-corner distances, "
            f"expected={self.expected_distance_mm:.2f}mm):\n"
            f"    Signed error:   mean={self.mean_error_mm:+.3f}mm  "
            f"median={self.median_error_mm:+.3f}mm  std={self.std_error_mm:.3f}mm\n"
            f"    Absolute error: mean={self.mean_abs_error_mm:.3f}mm  "
            f"median={self.median_abs_error_mm:.3f}mm  max={self.max_abs_error_mm:.3f}mm\n"
            f"    Within 1mm: {self.pct_within_1mm:.1f}%  "
            f"Within 5mm: {self.pct_within_5mm:.1f}%"
        )


class CalibrationHealthReport(BaseModel):
    """Full health report for one calibration result."""

    model_config = ConfigDict(extra="forbid")

    label: str
    reprojection_error_px: float
    n_observations_used: int
    n_observations_rejected: int
    time_seconds: float
    per_camera: list[PerCameraHealth]
    board_reconstruction: BoardReconstructionHealth | None

    @property
    def summary(self) -> str:
        lines = [
            f"--- {self.label} ---",
            f"  Reprojection error: {self.reprojection_error_px:.4f}px "
            f"({self.n_observations_used} obs used, {self.n_observations_rejected} rejected)",
            f"  Solver time: {self.time_seconds:.2f}s",
        ]
        if self.board_reconstruction is not None:
            lines.append(self.board_reconstruction.summary)
        for cam in self.per_camera:
            lines.append(cam.summary)
        return "\n".join(lines)


def compute_calibration_health(
    *,
    result: CalibrationResult,
    label: str,
    all_observations: list[CharucoCornersObservation] | None = None,
) -> CalibrationHealthReport:
    """Compute health metrics for a single calibration result.

    Args:
        result: The calibration to assess.
        label: Human-readable name (e.g. "Anipose", "Pyceres").
        all_observations: If provided, runs board reconstruction accuracy test.
    """
    per_camera: list[PerCameraHealth] = []
    for cam in result.cameras:
        i = cam.intrinsics
        w, h = cam.image_size

        # Focal length sanity: should be roughly image-width-ish (0.5x to 2x)
        avg_focal = (i.fx + i.fy) / 2.0
        focal_reasonable = (w * 0.5) < avg_focal < (w * 3.0)

        # Principal point sanity: should be near image center (within 25%)
        cx_dev = abs(i.cx - w / 2.0) / w
        cy_dev = abs(i.cy - h / 2.0) / h
        pp_reasonable = cx_dev < 0.25 and cy_dev < 0.25

        fx_fy_ratio = i.fx / i.fy if i.fy != 0 else float("inf")

        per_camera.append(PerCameraHealth(
            camera_name=cam.name,
            fx=i.fx, fy=i.fy, cx=i.cx, cy=i.cy,
            k1=i.k1, k2=i.k2,
            image_width=w, image_height=h,
            focal_length_reasonable=focal_reasonable,
            principal_point_reasonable=pp_reasonable,
            fx_fy_ratio=fx_fy_ratio,
        ))

    # Board reconstruction test
    board_health: BoardReconstructionHealth | None = None
    if all_observations is not None and len(all_observations) > 0:
        errors = _compute_board_distance_errors(
            cameras=result.cameras,
            board=result.board,
            all_observations=all_observations,
        )
        if len(errors) > 0:
            abs_errors = np.abs(errors)
            board_health = BoardReconstructionHealth(
                n_distance_measurements=len(errors),
                expected_distance_mm=result.board.square_length_mm,
                mean_error_mm=float(np.mean(errors)),
                median_error_mm=float(np.median(errors)),
                std_error_mm=float(np.std(errors)),
                mean_abs_error_mm=float(np.mean(abs_errors)),
                median_abs_error_mm=float(np.median(abs_errors)),
                max_abs_error_mm=float(np.max(abs_errors)),
                pct_within_1mm=float(np.mean(abs_errors < 1.0) * 100),
                pct_within_5mm=float(np.mean(abs_errors < 5.0) * 100),
            )

    return CalibrationHealthReport(
        label=label,
        reprojection_error_px=result.reprojection_error_px,
        n_observations_used=result.n_observations_used,
        n_observations_rejected=result.n_observations_rejected,
        time_seconds=result.time_seconds,
        per_camera=per_camera,
        board_reconstruction=board_health,
    )


# =============================================================================
# PER-CAMERA COMPARISON
# =============================================================================


class CameraComparisonResult(BaseModel):
    """Side-by-side comparison of a single camera across two calibrations."""

    model_config = ConfigDict(extra="forbid")

    camera_name: str

    fx_a: float
    fx_b: float
    fy_a: float
    fy_b: float
    cx_a: float
    cx_b: float
    cy_a: float
    cy_b: float
    k1_a: float
    k1_b: float
    k2_a: float
    k2_b: float

    world_position_a: list[float]
    world_position_b: list[float]

    focal_length_delta_px: float
    principal_point_delta_px: float
    world_position_delta_mm: float
    rotation_angle_delta_deg: float

    @property
    def summary(self) -> str:
        return (
            f"  Camera '{self.camera_name}':\n"
            f"    Focal length:     A=({self.fx_a:.1f}, {self.fy_a:.1f})  "
            f"B=({self.fx_b:.1f}, {self.fy_b:.1f})  "
            f"Δ={self.focal_length_delta_px:.2f}px\n"
            f"    Principal point:  A=({self.cx_a:.1f}, {self.cy_a:.1f})  "
            f"B=({self.cx_b:.1f}, {self.cy_b:.1f})  "
            f"Δ={self.principal_point_delta_px:.2f}px\n"
            f"    Distortion k1:   A={self.k1_a:.6f}  B={self.k1_b:.6f}\n"
            f"    Distortion k2:   A={self.k2_a:.6f}  B={self.k2_b:.6f}\n"
            f"    World position:  Δ={self.world_position_delta_mm:.1f}mm\n"
            f"    Rotation:        Δ={self.rotation_angle_delta_deg:.2f}°"
        )


# =============================================================================
# AGGREGATE COMPARISON
# =============================================================================


class CalibrationComparisonResult(BaseModel):
    """Full comparison between two calibration results."""

    model_config = ConfigDict(extra="forbid")

    health_a: CalibrationHealthReport
    health_b: CalibrationHealthReport

    per_camera: list[CameraComparisonResult]

    mean_focal_length_delta_px: float
    max_focal_length_delta_px: float
    mean_world_position_delta_mm: float
    max_world_position_delta_mm: float
    mean_rotation_delta_deg: float
    max_rotation_delta_deg: float

    @property
    def summary(self) -> str:
        label_a = self.health_a.label
        label_b = self.health_b.label

        lines = [
            "=" * 70,
            f"CALIBRATION COMPARISON: {label_a} vs {label_b}",
            "=" * 70,
            "",
            self.health_a.summary,
            "",
            self.health_b.summary,
            "",
            "--- Agreement between solvers ---",
            f"  Focal length:    mean Δ={self.mean_focal_length_delta_px:.2f}px  "
            f"max Δ={self.max_focal_length_delta_px:.2f}px",
            f"  World position:  mean Δ={self.mean_world_position_delta_mm:.1f}mm  "
            f"max Δ={self.max_world_position_delta_mm:.1f}mm",
            f"  Rotation:        mean Δ={self.mean_rotation_delta_deg:.2f}°  "
            f"max Δ={self.max_rotation_delta_deg:.2f}°",
            "",
            "--- Per-camera deltas ---",
        ]
        for cam in self.per_camera:
            lines.append(cam.summary)
        lines.append("=" * 70)
        return "\n".join(lines)


# =============================================================================
# COMPARISON FUNCTION
# =============================================================================


def _rotation_angle_between(
    rmat_a: NDArray[np.float64],
    rmat_b: NDArray[np.float64],
) -> float:
    """Angle in degrees between two rotation matrices."""
    R_diff = rmat_a @ rmat_b.T
    trace = np.clip(np.trace(R_diff), -1.0, 3.0)
    angle_rad = np.arccos((trace - 1.0) / 2.0)
    return float(np.degrees(angle_rad))


def _compare_single_camera(
    cam_a: CameraModel,
    cam_b: CameraModel,
) -> CameraComparisonResult:
    """Compare a single camera across two calibrations."""
    ia = cam_a.intrinsics
    ib = cam_b.intrinsics

    focal_delta = np.sqrt((ia.fx - ib.fx) ** 2 + (ia.fy - ib.fy) ** 2)
    pp_delta = np.sqrt((ia.cx - ib.cx) ** 2 + (ia.cy - ib.cy) ** 2)

    pos_a = cam_a.extrinsics.world_position
    pos_b = cam_b.extrinsics.world_position
    pos_delta = float(np.linalg.norm(pos_a - pos_b))

    rot_delta = _rotation_angle_between(
        cam_a.extrinsics.rotation_matrix,
        cam_b.extrinsics.rotation_matrix,
    )

    return CameraComparisonResult(
        camera_name=cam_a.name,
        fx_a=ia.fx, fx_b=ib.fx,
        fy_a=ia.fy, fy_b=ib.fy,
        cx_a=ia.cx, cx_b=ib.cx,
        cy_a=ia.cy, cy_b=ib.cy,
        k1_a=ia.k1, k1_b=ib.k1,
        k2_a=ia.k2, k2_b=ib.k2,
        world_position_a=pos_a.tolist(),
        world_position_b=pos_b.tolist(),
        focal_length_delta_px=float(focal_delta),
        principal_point_delta_px=float(pp_delta),
        world_position_delta_mm=pos_delta,
        rotation_angle_delta_deg=rot_delta,
    )


def compare_calibration_results(
    *,
    result_a: CalibrationResult,
    result_b: CalibrationResult,
    label_a: str = "A",
    label_b: str = "B",
    all_observations: list[CharucoCornersObservation] | None = None,
) -> CalibrationComparisonResult:
    """Compare two calibration results with full health reports.

    Both results must have the same camera names (order doesn't matter).

    Args:
        result_a: First calibration result.
        result_b: Second calibration result.
        label_a: Label for first result.
        label_b: Label for second result.
        all_observations: If provided, runs board reconstruction accuracy
            test for both calibrations using the same observations.
    """
    names_a = set(result_a.camera_names)
    names_b = set(result_b.camera_names)
    if names_a != names_b:
        raise ValueError(
            f"Camera name mismatch: {label_a} has {sorted(names_a)}, "
            f"{label_b} has {sorted(names_b)}"
        )

    # Health reports
    health_a = compute_calibration_health(
        result=result_a,
        label=label_a,
        all_observations=all_observations,
    )
    health_b = compute_calibration_health(
        result=result_b,
        label=label_b,
        all_observations=all_observations,
    )

    # Per-camera comparison
    per_camera: list[CameraComparisonResult] = []
    for name in sorted(names_a):
        cam_a = result_a.get_camera(name)
        cam_b = result_b.get_camera(name)
        per_camera.append(_compare_single_camera(cam_a=cam_a, cam_b=cam_b))

    focal_deltas = [c.focal_length_delta_px for c in per_camera]
    pos_deltas = [c.world_position_delta_mm for c in per_camera]
    rot_deltas = [c.rotation_angle_delta_deg for c in per_camera]

    return CalibrationComparisonResult(
        health_a=health_a,
        health_b=health_b,
        per_camera=per_camera,
        mean_focal_length_delta_px=float(np.mean(focal_deltas)),
        max_focal_length_delta_px=float(np.max(focal_deltas)),
        mean_world_position_delta_mm=float(np.mean(pos_deltas)),
        max_world_position_delta_mm=float(np.max(pos_deltas)),
        mean_rotation_delta_deg=float(np.mean(rot_deltas)),
        max_rotation_delta_deg=float(np.max(rot_deltas)),
    )