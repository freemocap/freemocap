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
    # When True, skeleton inference runs in a single dedicated worker process
    # that batches frames from all cameras (one CUDA context, one ONNX session).
    # When False, each camera node runs its own RTMPoseDetector inline (legacy
    # behavior; suitable for CPU-only machines or for A/B comparison).
    use_centralized_gpu_inference: bool = True
    log_pipeline_times: bool = True

    skeleton_inference_node_config: RealtimeSkeletonInferenceNodeConfig = Field(
        default_factory=RealtimeSkeletonInferenceNodeConfig,
    )
