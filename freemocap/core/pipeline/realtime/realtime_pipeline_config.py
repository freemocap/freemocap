from typing import Literal

from pydantic import BaseModel, Field, model_validator

from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import RealtimeAggregatorNodeConfig
from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node_config import (
    RealtimeSkeletonInferenceNodeConfig,
)


class RealtimePipelineConfig(BaseModel):
    """Realtime pipeline settings.

    ``realtime_detector_kind`` / ``realtime_model_size`` are mirrored into
    ``camera_node_config`` on validation so worker processes that only read
    ``CameraNodeConfig`` stay in sync.
    """

    realtime_detector_kind: Literal["rtmpose", "mediapipe_js"] = "rtmpose"
    realtime_model_size: Literal["lite", "full", "heavy"] = "full"

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

    @model_validator(mode="after")
    def _sync_detector_fields_into_camera_node_config(self) -> "RealtimePipelineConfig":
        self.camera_node_config = self.camera_node_config.model_copy(
            update={
                "realtime_detector_kind": self.realtime_detector_kind,
                "realtime_model_size": self.realtime_model_size,
                "use_centralized_gpu_inference": self.use_centralized_gpu_inference,
            },
        )
        return self
