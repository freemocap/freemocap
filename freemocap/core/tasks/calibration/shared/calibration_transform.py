"""Recorded scene transformations, in reconstruction axes and millimeters."""

from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, FiniteFloat, model_validator
from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion
from skellyforge.core.math.geometry.spatial_vectors import Displacement
from skellyforge.core.math.geometry.transform_math import Transform


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
