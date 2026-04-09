from pydantic import BaseModel, Field
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import RealtimeAggregatorNodeConfig


class RealtimePipelineConfig(BaseModel):
    camera_configs: CameraConfigs

    camera_node_config: CameraNodeConfig = Field(
        default_factory=CameraNodeConfig,
    )
    aggregator_config: RealtimeAggregatorNodeConfig = Field(
        default_factory=RealtimeAggregatorNodeConfig,
    )

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_configs.keys())

    @classmethod
    def from_camera_configs(cls, *, camera_configs: CameraConfigs) -> "RealtimePipelineConfig":
        return cls(camera_configs=camera_configs)
