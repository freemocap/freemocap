from pydantic import BaseModel, Field, model_validator

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

    @model_validator(mode="after")
    def validate_dlc_execution(self):
        if self.camera_node_config.detector_type == "dlc":
            if self.skeleton_inference_node_config.execution_provider not in ("cpu", "cuda"):
                raise ValueError("DLC requires an explicit CPU or CUDA execution provider (FP32)")
            if self.aggregator_config.skeleton_fitting_enabled and not self.camera_node_config.dlc_geometry_path:
                raise ValueError("DLC skeleton fitting requires an explicit object geometry association; disable skeleton fitting for model-only keypoints")
        return self
