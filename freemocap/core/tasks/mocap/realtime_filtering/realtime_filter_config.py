"""Authoritative realtime processing settings; all numerical units are explicit."""
from pydantic import BaseModel, ConfigDict, Field

class OneEuroConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    enabled: bool = True
    min_cutoff: float = Field(default=1.0, gt=0, description='Minimum cutoff in Hz')
    beta: float = Field(default=0.01, ge=0, description='Speed coefficient in inverse coordinate units')
    d_cutoff: float = Field(default=1.0, gt=0, description='Derivative cutoff in Hz')

class RealtimeFilterConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    # Tune slow-motion jitter first, then fast-motion lag [@casiezOneEuroTuning].
    image_smoothing: OneEuroConfig = Field(default_factory=lambda: OneEuroConfig(enabled=False, beta=0.03),
        description='Image smoothing; coordinates in pixels, beta in inverse pixels')
    spatial_smoothing: OneEuroConfig = Field(default_factory=OneEuroConfig,
        description='Spatial smoothing; coordinates in millimeters, beta in inverse millimeters')
    velocity_gate_enabled: bool = True
    max_velocity_mm_per_s: float = Field(default=50000.0, gt=0)
    reacquisition_timeout_s: float = Field(default=0.3, gt=0)
    gap_duration_s: float = Field(default=0.3, ge=0, le=2, description='Maximum age since accepted input; zero disables recovery')
    prediction_duration_s: float = Field(default=0.1, ge=0, le=2, description='Extrapolation horizon before holding position')
    velocity_half_life_s: float = Field(default=0.08, gt=0, description='Predicted velocity half-life in seconds')
    segment_retention_s: float = Field(default=0.3, ge=0, le=2, description='Maximum age of retained segment poses')
    max_reprojection_error_px: float = Field(default=60.0, gt=0)
    segment_scale_window_frames: int = Field(default=30, ge=1)
