from pydantic import BaseModel, Field
from freemocap.core.reconstruction.reference_transform import ReferenceTransform

from freemocap.core.tasks.mocap.realtime_filtering.realtime_filter_config import RealtimeFilterConfig
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.tasks.calibration.camera_matching.matching_models import CameraMatchingConfig


class RealtimeAggregatorNodeConfig(BaseModel):
    anchor_segment_name: str = Field(default="pelvis", min_length=1,
        description="Human segment whose measured origin anchors connected reconstruction.")
    reference_transform: ReferenceTransform | None = None
    camera_matching: CameraMatchingConfig = Field(default_factory=CameraMatchingConfig)
    calibration_toml_path: str | None = Field(
        default=None,
        description="Selected calibration TOML to load and watch. None disables calibrated triangulation.",
    )
    triangulation_enabled: bool = True
    filter_enabled: bool = False
    center_of_mass_enabled: bool = True
    skeleton_fitting_enabled: bool = False

    realtime_filter_config: RealtimeFilterConfig = Field(default_factory=RealtimeFilterConfig)
    triangulation_config: TriangulationConfig = Field(default_factory=TriangulationConfig)
