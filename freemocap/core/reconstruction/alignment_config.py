"""Mocap alignment controls shared by processing modes."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from skellyforge.core.biomechanics.body_alignment import BodyAlignmentConfig
from skellyforge.core.biomechanics.ground_alignment import GroundAlignmentConfig

from freemocap.core.reconstruction.reference_transform import ReferenceTransform


def default_ground_config() -> GroundAlignmentConfig:
    """Contact thresholds in millimeters and seconds."""
    return GroundAlignmentConfig(maximum_speed=50.0, maximum_plane_distance=15.0, minimum_spread=20.0)


class MocapAlignmentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal['auto', 'calibration', 'person'] = 'auto'
    additional_transform: ReferenceTransform | None = None
    reprojection_scale_px: float = Field(default=5.0, gt=0, allow_inf_nan=False)
    body: BodyAlignmentConfig = Field(default_factory=BodyAlignmentConfig)
    ground: GroundAlignmentConfig = Field(default_factory=default_ground_config)

    @model_validator(mode='before')
    @classmethod
    def accept_legacy_enabled(cls, value):
        if isinstance(value, dict) and 'enabled' in value:
            if 'mode' in value:
                raise ValueError('Specify alignment mode or legacy enabled, not both')
            value = dict(value)
            enabled = value.pop('enabled')
            if not isinstance(enabled, bool):
                raise ValueError('Legacy alignment enabled must be a boolean')
            value['mode'] = 'person' if enabled else 'calibration'
        return value

    @property
    def enabled(self) -> bool:
        """Whether person estimation is permitted; auto also checks calibration."""
        return self.mode != 'calibration'

    def preserve_reference_frame(self, *, calibration_aligned: bool) -> bool:
        return self.mode == 'calibration' or (self.mode == 'auto' and calibration_aligned)
