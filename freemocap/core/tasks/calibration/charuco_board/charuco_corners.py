import numpy as np
from numpy._typing import NDArray
from pydantic import BaseModel, ConfigDict, field_validator


class CornerObservation(BaseModel):
    """A single detected charuco corner in pixel coordinates."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    corner_id: int
    pixel_xy: NDArray[np.float64]

    @field_validator("pixel_xy", mode="before")
    @classmethod
    def validate_pixel(cls, v: NDArray[np.float64] | list | tuple) -> NDArray[np.float64]:
        arr = np.asarray(v, dtype=np.float64).ravel()
        if arr.shape != (2,):
            raise ValueError(f"pixel_xy must have shape (2,), got {arr.shape}")
        return arr


class CharucoCornersObservation(BaseModel):
    """All charuco corners detected by one camera in one frame."""

    model_config = ConfigDict(extra="forbid")

    camera_name: str
    frame_index: int
    corners: list[CornerObservation]

    @property
    def n_corners(self) -> int:
        return len(self.corners)

    @property
    def corner_ids(self) -> list[int]:
        return [c.corner_id for c in self.corners]
