from pydantic import BaseModel, Field
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.pipeline_configs.calibration_task_config import CalibrationPipelineConfig
from freemocap.core.pipeline.pipeline_configs.mocap_task_config import MocapPipelineConfig


class RealtimePipelineConfig(BaseModel):
    camera_configs: CameraConfigs

    calibration_config: CalibrationPipelineConfig = Field(
        default_factory=CalibrationPipelineConfig,
    )
    mocap_config: MocapPipelineConfig = Field(
        default_factory=MocapPipelineConfig.default_realtime,
    )
    calibration_detection_enabled: bool = Field(default=True)
    mocap_detection_enabled: bool = Field(default=True)

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_configs.keys())

    @classmethod
    def from_camera_configs(cls, *, camera_configs: CameraConfigs) -> "RealtimePipelineConfig":
        return cls(camera_configs=camera_configs)
