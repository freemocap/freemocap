"""Validated output-frame offsets in reconstruction axes and millimeters."""

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion
from skellyforge.core.math.geometry.spatial_vectors import Displacement
from skellyforge.core.math.geometry.transform_math import Transform


class ReferenceTransform(BaseModel):
    """Row-major homogeneous matrix; column vectors map as X' = R X + t."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    matrix: tuple[float, ...] = Field(min_length=16, max_length=16)

    @model_validator(mode="after")
    def validate_rigid_transform(self) -> "ReferenceTransform":
        matrix = np.asarray(self.matrix, dtype=np.float64).reshape(4, 4)
        rotation = matrix[:3, :3]
        if not np.allclose(matrix[3], [0, 0, 0, 1], atol=1e-5, rtol=0):
            raise ValueError("Transform bottom row must be [0, 0, 0, 1]")
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5, rtol=0) or not np.isclose(
            np.linalg.det(rotation), 1.0, atol=1e-5, rtol=0
        ):
            raise ValueError("Transform rotation must be orthonormal, without scale, shear or reflection")
        return self

    def to_transform(self) -> Transform:
        matrix = np.asarray(self.matrix, dtype=np.float64).reshape(4, 4)
        return Transform(
            rotation=RotationQuaternion.from_rotation_matrix(matrix=matrix[:3, :3]),
            translation=Displacement.from_prevalidated_array(array=matrix[:3, 3]),
        )
