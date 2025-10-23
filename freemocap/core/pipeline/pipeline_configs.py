from pydantic import BaseModel
from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.charuco_tracker import CharucoTrackerConfig


class CalibrationPipelineCameraNodeConfig(BaseModel):
    camera_config: CameraConfig
    tracker_config: CharucoTrackerConfig


class CalibrationAggregationNodeConfig(BaseModel):
    pass



class CameraNodeConfig(BaseModel):
    pass


class AggregationNodeConfig(BaseModel):
    pass


class PipelineTaskConfig(BaseModel):
    camera_node_configs: dict[CameraIdString, CameraNodeConfig]
    aggregation_node_config: AggregationNodeConfig


class CalibrationPipelineTaskConfig(PipelineTaskConfig):
    camera_node_configs: dict[CameraIdString, CalibrationPipelineCameraNodeConfig]
    aggregation_node_config: CalibrationAggregationNodeConfig

    @classmethod
    def create(cls,
               camera_configs: CameraConfigs,
               tracker_config: CharucoTrackerConfig):
        return cls(camera_node_configs={camera_id: CalibrationPipelineCameraNodeConfig(camera_config=camera_config,
                                                                                       tracker_config=tracker_config)
                                        for camera_id, camera_config in camera_configs.items()},
                   aggregation_node_config=CalibrationAggregationNodeConfig())


class PipelineConfig(BaseModel):
    calibration_task_config: CalibrationPipelineTaskConfig
    mocap_task_config: PipelineTaskConfig | None = None
    @classmethod
    def create(cls,
               camera_configs:CameraConfigs,
               charuco_tracker_config: CharucoTrackerConfig|None = None):
        return cls(
            calibration_task_config=CalibrationPipelineTaskConfig.create(
                camera_configs=camera_configs,
                tracker_config=charuco_tracker_config or CharucoTrackerConfig()
            )
        )
