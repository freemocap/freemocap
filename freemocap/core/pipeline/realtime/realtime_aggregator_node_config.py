from pydantic import BaseModel, Field

from freemocap.core.tasks.mocap.realtime_filtering.realtime_filter_config import RealtimeFilterConfig
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig


class RealtimeAggregatorNodeConfig(BaseModel):
    calibration_toml_path: str | None = Field(
        default=None,
        description="Path to calibration TOML. If None, the most-recent successful calibration is used (and hot-reloaded).",
    )
    triangulation_enabled: bool = True
    filter_enabled: bool = False
    center_of_mass_enabled: bool = True
    skeleton_fitting_enabled: bool = True

    realtime_filter_config: RealtimeFilterConfig = Field(default_factory=RealtimeFilterConfig)
    triangulation_config: TriangulationConfig = Field(default_factory=TriangulationConfig)
