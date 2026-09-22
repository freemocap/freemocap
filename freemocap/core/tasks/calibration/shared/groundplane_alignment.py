"""Shared ground plane alignment for camera calibration.

Provides GroundPlaneResult, the output of ground plane estimation.

Used by both charuco-based and feet-based ground plane estimation.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, FiniteFloat


class CalibrationAlignmentMethod(str, Enum):
    CHARUCO = "charuco"
    PERSON = "person"


class GroundPlaneResult(BaseModel):
    """Result of ground plane estimation from any method."""

    model_config = ConfigDict(extra="forbid")

    origin: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    rotation_matrix: tuple[
        tuple[FiniteFloat, FiniteFloat, FiniteFloat],
        tuple[FiniteFloat, FiniteFloat, FiniteFloat],
        tuple[FiniteFloat, FiniteFloat, FiniteFloat],
    ]
    method: CalibrationAlignmentMethod
