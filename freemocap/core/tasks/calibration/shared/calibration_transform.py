"""Recorded scene transformations, in reconstruction axes and millimeters."""

from enum import Enum
from typing import Self

import numpy as np

from pydantic import BaseModel, ConfigDict, FiniteFloat, model_validator
from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion
from skellyforge.core.math.geometry.spatial_vectors import Displacement
from skellyforge.core.math.geometry.transform_math import Transform

from freemocap.core.reconstruction.coordinate_conventions import (
    CALIBRATION_TO_RECONSTRUCTION,
    RECONSTRUCTION_TO_CALIBRATION,
)
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.calibration.shared.groundplane_alignment import GroundPlaneResult


class CalibrationTransformType(str, Enum):
    CHARUCO = "charuco"
    PERSON = "person"
    MANUAL = "manual"


class CalibrationTransform(BaseModel):
    """One applied X' = R X + t operation; history is ordered oldest first.

    Coordinates: X right, Y forward, Z up. Translation is in millimeters.
    Quaternion components are scalar-first: w, x, y, z.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: CalibrationTransformType
    quaternion_wxyz: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]
    translation_mm: tuple[FiniteFloat, FiniteFloat, FiniteFloat]

    @model_validator(mode="after")
    def validate_rotation(self) -> Self:
        w, x, y, z = self.quaternion_wxyz
        RotationQuaternion(w=w, x=x, y=y, z=z)
        return self

    @classmethod
    def from_transform(
        cls, *, operation: CalibrationTransformType, transform: Transform,
    ) -> Self:
        return cls(
            operation=operation,
            quaternion_wxyz=tuple(transform.rotation.as_array()),
            translation_mm=tuple(transform.translation.array),
        )

    def to_transform(self) -> Transform:
        w, x, y, z = self.quaternion_wxyz
        tx, ty, tz = self.translation_mm
        return Transform(
            rotation=RotationQuaternion(w=w, x=x, y=y, z=z),
            translation=Displacement.from_xyz(x=tx, y=ty, z=tz),
        )

    @classmethod
    def from_ground_plane(cls, *, result: GroundPlaneResult) -> Self:
        """Convert the estimated plane pose into the applied world-to-plane transform."""
        ox, oy, oz = result.origin
        plane_to_world = Transform(
            rotation=RotationQuaternion.from_rotation_matrix(
                matrix=np.asarray(result.rotation_matrix, dtype=np.float64),
            ),
            translation=Displacement.from_xyz(x=ox, y=oy, z=oz),
        )
        applied = plane_to_world.inverse()
        return cls.from_transform(
            operation=CalibrationTransformType(result.method.value),
            transform=Transform(
                rotation=CALIBRATION_TO_RECONSTRUCTION.convert_quaternion(
                    quaternion=applied.rotation,
                ),
                translation=CALIBRATION_TO_RECONSTRUCTION.convert_displacement(
                    displacement=applied.translation,
                ),
            ),
        )

    def apply_to_cameras(self, *, cameras: list[CameraModel]) -> list[CameraModel]:
        """Return cameras expressed in the transformed frame; leave inputs untouched."""
        transform = self.to_transform()
        calibration_transform = Transform(
            rotation=RECONSTRUCTION_TO_CALIBRATION.convert_quaternion(
                quaternion=transform.rotation,
            ),
            translation=RECONSTRUCTION_TO_CALIBRATION.convert_displacement(
                displacement=transform.translation,
            ),
        )
        return [camera.in_world_frame(transform=calibration_transform) for camera in cameras]
