from pydantic import BaseModel, Field

from freemocap.core.tasks.calibration.calibration_task_config import CalibrationSource
from freemocap.core.tasks.mocap.skeleton_dewiggler.realtime_skeleton_filter import RealtimeFilterConfig


class RealtimeAggregatorNodeConfig(BaseModel):
    calibration_toml_source:CalibrationSource = Field(
        default=CalibrationSource.MOST_RECENT,
        alias="calibrationTomlSource",
        description="How to select the calibration TOML for this node: 'most_recent' uses the latest successful calibration, 'specified' uses calibrationTomlPath.",
    )
    calibration_toml_path: str | None = Field(
        default=None,
        alias="calibrationTomlPath",
        description="Path to calibration TOML. Only used when calibrationTomlSource is 'specified'.",
    )
    triangulation_enabled: bool = True
    filter_enabled: bool = False
    skeleton_enabled: bool = True

    realtime_filter_config: RealtimeFilterConfig = Field(default_factory=RealtimeFilterConfig)
