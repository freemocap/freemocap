"""Mocap alignment controls shared by processing modes."""

from pydantic import BaseModel, ConfigDict, Field
from skellyforge.core.biomechanics.body_alignment import BodyAlignmentConfig
from skellyforge.core.biomechanics.ground_alignment import GroundAlignmentConfig


def default_ground_config() -> GroundAlignmentConfig:
    """Contact thresholds in millimeters and seconds."""
    return GroundAlignmentConfig(maximum_speed=50.0, maximum_plane_distance=15.0, minimum_spread=20.0)


class MocapAlignmentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    reprojection_scale_px: float = Field(default=5.0, gt=0, allow_inf_nan=False)
    body: BodyAlignmentConfig = Field(default_factory=BodyAlignmentConfig)
    ground: GroundAlignmentConfig = Field(default_factory=default_ground_config)
