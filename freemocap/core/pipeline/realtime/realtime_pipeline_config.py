from pydantic import BaseModel, Field
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import RealtimeAggregatorNodeConfig
from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node_config import (
    RealtimeSkeletonInferenceNodeConfig,
)


class RealtimePipelineConfig(BaseModel):
    camera_node_config: CameraNodeConfig = Field(
        default_factory=CameraNodeConfig,
    )
    aggregator_config: RealtimeAggregatorNodeConfig = Field(
        default_factory=RealtimeAggregatorNodeConfig,
    )
    # When True, skeleton inference runs in a single dedicated worker process that
    # reads all camera ring buffers directly and dispatches inference via process_batch.
    # When False, each camera node runs its own tracker inline (legacy per-process path).
    use_centralized_inference: bool = True
    log_pipeline_times: bool = True

    skeleton_inference_node_config: RealtimeSkeletonInferenceNodeConfig = Field(
        default_factory=RealtimeSkeletonInferenceNodeConfig,
    )
