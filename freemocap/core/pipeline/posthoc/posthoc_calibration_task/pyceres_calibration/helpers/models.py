"""Pyceres-specific data models for camera calibration via bundle adjustment.

Shared types (CharucoBoardDefinition, CameraIntrinsics, CameraExtrinsics,
CameraModel, CornerObservation, CharucoCornersObservation, CalibrationResult)
are imported from shared.models and re-exported here for backward compatibility.
"""

from pydantic import BaseModel, ConfigDict, model_validator

from freemocap.core.pipeline.posthoc.posthoc_calibration_task.shared.calibration_models import (  # noqa: F401
    CalibrationResult,
    CameraExtrinsics,
    CameraIntrinsics,
    CameraModel,
    CharucoBoardDefinition,
    CharucoCornersObservation,
    CornerObservation,
)


# =============================================================================
# PYCERES-SPECIFIC: INTRINSICS OPTIMIZATION MODE
# =============================================================================


class IntrinsicsOptimizationMode(BaseModel):
    """Control which intrinsic parameters are free during optimization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    optimize_focal_length: bool = True
    shared_focal_length: bool = False
    optimize_principal_point: bool = False
    optimize_k1: bool = False
    optimize_k2: bool = False
    optimize_tangential: bool = False

    @property
    def constant_indices(self) -> list[int]:
        """Indices into the 8-element intrinsics array that should be held constant.

        Array layout: [fx, fy, cx, cy, k1, k2, p1, p2]
        """
        indices: list[int] = []
        if not self.optimize_focal_length:
            indices.extend([0, 1])
        if not self.optimize_principal_point:
            indices.extend([2, 3])
        if not self.optimize_k1:
            indices.append(4)
        if not self.optimize_k2:
            indices.append(5)
        if not self.optimize_tangential:
            indices.extend([6, 7])
        return sorted(indices)


# =============================================================================
# PYCERES-SPECIFIC: SOLVER CONFIG
# =============================================================================


class PyceresCalibrationSolverConfig(BaseModel):
    """Configuration for the pyceres bundle adjustment solver."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_iterations: int = 100
    function_tolerance: float = 1e-6
    parameter_tolerance: float = 1e-8
    gradient_tolerance: float = 1e-10
    intrinsics_mode: IntrinsicsOptimizationMode = IntrinsicsOptimizationMode()
    intrinsics_prior_weight: float = 0.01
    pin_camera_0: bool = True
    outlier_rejection_iterations: int = 5
    initial_outlier_threshold_px: float = 15.0
    final_outlier_threshold_px: float = 2.0
    min_corners_per_frame: int = 4
    verbose: bool = True

    @model_validator(mode="after")
    def validate_thresholds(self) -> "PyceresCalibrationSolverConfig":
        if self.initial_outlier_threshold_px < self.final_outlier_threshold_px:
            raise ValueError(
                f"initial_outlier_threshold_px ({self.initial_outlier_threshold_px}) "
                f"must be >= final_outlier_threshold_px ({self.final_outlier_threshold_px})"
            )
        return self
