from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from freemocap.core.tasks.calibration.shared.transform_math import make_M


class AniposeCamera(BaseModel):
    """Camera model for anipose-style calibration, backed by Pydantic v2."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    # --- Fields ----------------------------------------------------------- #

    camera_matrix: np.ndarray = Field(
        default_factory=lambda: np.eye(3, dtype=np.float64),
        alias="matrix",
        description="3×3 intrinsic camera matrix (legacy name: matrix)",
    )
    distortion_coefficients: np.ndarray = Field(
        default_factory=lambda: np.zeros(5, dtype=np.float64),
        alias="dist",
        description="Distortion coefficients, up to 5 values (legacy name: dist)",
    )
    size: tuple[int, int] | None = Field(
        description="Image size as (width, height)",
    )
    rotation_vector: np.ndarray = Field(
        default_factory=lambda: np.zeros(3, dtype=np.float64),
        alias="rvec",
        description="Rodrigues rotation vector, 3-element (legacy name: rvec)",
    )
    translation_vector: np.ndarray = Field(
        default_factory=lambda: np.zeros(3, dtype=np.float64),
        alias="tvec",
        description="Translation vector, 3-element (legacy name: tvec)",
    )
    world_orientation: np.ndarray = Field(
        default_factory=lambda: np.eye(3, dtype=np.float64),
        description="3×3 world-frame orientation matrix",
    )
    world_position: np.ndarray = Field(
        default_factory=lambda: np.zeros(3, dtype=np.float64),
        description="World-frame position, 3-element",
    )
    id: str = Field(
        alias="name",
        description="Camera identifier",
    )
    extra_dist: bool = Field(
        default=False,
        description="Whether a second distortion coefficient is optimised",
    )

    # --- Validators ------------------------------------------------------- #

    @field_validator("camera_matrix", mode="before")
    @classmethod
    def _coerce_camera_matrix(cls, v: Any) -> np.ndarray:
        return np.asarray(v, dtype=np.float64).reshape(3, 3)

    @field_validator("distortion_coefficients", mode="before")
    @classmethod
    def _coerce_distortion_coefficients(cls, v: Any) -> np.ndarray:
        return np.asarray(v, dtype=np.float64).ravel()

    @field_validator("rotation_vector", mode="before")
    @classmethod
    def _coerce_rotation_vector(cls, v: Any) -> np.ndarray:
        return np.asarray(v, dtype=np.float64).ravel()

    @field_validator("translation_vector", mode="before")
    @classmethod
    def _coerce_translation_vector(cls, v: Any) -> np.ndarray:
        return np.asarray(v, dtype=np.float64).ravel()

    @field_validator("world_orientation", mode="before")
    @classmethod
    def _coerce_world_orientation(cls, v: Any) -> np.ndarray:
        return np.asarray(v, dtype=np.float64).reshape(3, 3)

    @field_validator("world_position", mode="before")
    @classmethod
    def _coerce_world_position(cls, v: Any) -> np.ndarray:
        return np.asarray(v, dtype=np.float64).ravel()

    # --- Computed properties ---------------------------------------------- #

    @property
    def focal_length(self) -> float:
        """Average focal length (fx+fy)/2."""
        return (self.camera_matrix[0, 0] + self.camera_matrix[1, 1]) / 2.0

    @focal_length.setter
    def focal_length(self, value: float) -> None:
        self.camera_matrix[0, 0] = value
        self.camera_matrix[1, 1] = value

    @property
    def extrinsics_matrix(self) -> np.ndarray:
        """4×4 extrinsics matrix built from rotation_vector and translation_vector."""
        return make_M(self.rotation_vector, self.translation_vector)

    # --- Serialization ---------------------------------------------------- #

    def to_dict(self) -> dict[str, Any]:
        """Serialise camera parameters to a plain dict."""
        return {
            "name": self.name,
            "size": list(self.size) if self.size is not None else None,
            "matrix": self.camera_matrix.tolist(),
            "distortions": self.distortion_coefficients.tolist(),
            "rotation": self.rotation_vector.tolist(),
            "translation": self.translation_vector.tolist(),
            "world_orientation": self.world_orientation.tolist(),
            "world_position": self.world_position.tolist(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AniposeCamera:
        """Construct an AniposeCamera from a serialised dict."""
        return cls(
            name=d["name"],
            size=tuple(d["size"]) if d.get("size") is not None else None,
            camera_matrix=d["matrix"],
            distortion_coefficients=d["distortions"],
            rotation_vector=d["rotation"],
            translation_vector=d["translation"],
            world_orientation=d.get("world_orientation", np.eye(3)),
            world_position=d.get("world_position", np.zeros(3)),
        )

    # --- Optimisation parameter packing ----------------------------------- #

    def get_params(self) -> np.ndarray:
        """Pack optimisable parameters into a flat array.

        Layout: [rotation_vector(3), translation_vector(3), focal_length(1), dist0(1), dist1?(1)]
        """
        params: np.ndarray = np.zeros(8 + self.extra_dist, dtype=np.float64)
        params[0:3] = self.rotation_vector
        params[3:6] = self.translation_vector
        params[6] = self.focal_length
        params[7] = self.distortion_coefficients[0]
        if self.extra_dist:
            params[8] = self.distortion_coefficients[1]
        return params

    def set_params(self, params: np.ndarray) -> None:
        """Unpack optimisable parameters from a flat array."""
        self.rotation_vector = np.asarray(params[0:3], dtype=np.float64).ravel()
        self.translation_vector = np.asarray(params[3:6], dtype=np.float64).ravel()
        self.focal_length = float(params[6])

        dist: np.ndarray = np.zeros(5, dtype=np.float64)
        dist[0] = params[7]
        if self.extra_dist:
            dist[1] = params[8]
        self.distortion_coefficients = dist
