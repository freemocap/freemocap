from pydantic import BaseModel, model_validator
from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.charuco_tracker import CharucoTrackerConfig
from skellytracker.trackers.charuco_tracker.charuco_annotator import CharucoAnnotatorConfig


class CameraNodeTaskConfig(BaseModel):
    camera_config: CameraConfig

class AggregationTaskConfig(BaseModel):
    camera_configs: CameraConfigs

class CalibrationCameraNodeConfig(CameraNodeTaskConfig):
    tracker_config: CharucoTrackerConfig
    annotator_config:CharucoAnnotatorConfig

class CalibrationAggregationNodeConfig(AggregationTaskConfig):
    pass

class MocapCameraNodeConfig(CameraNodeTaskConfig):
    pass

class MocapAggregationNodeConfig(AggregationTaskConfig):
    pass

class AggregationNodeConfig(BaseModel):
    camera_configs: CameraConfigs
    calibration_aggregation_node_config: CalibrationAggregationNodeConfig
    mocap_aggregation_node_config: MocapAggregationNodeConfig


class CameraNodeConfig(BaseModel):
    camera_config: CameraConfig
    calibration_camera_node_config: CalibrationCameraNodeConfig
    mocap_camera_node_config: MocapCameraNodeConfig

    @property
    def camera_id(self) -> CameraIdString:
        return self.camera_config.camera_id

    def create_image_annotater(self):
        raise NotImplementedError("Method create_image_annotator is not implemented yet.")

class PipelineConfig(BaseModel):
    camera_node_configs: dict[CameraIdString, CameraNodeConfig]
    aggregation_node_config: AggregationNodeConfig
    @property
    def camera_configs(self) -> CameraConfigs:
        return self.aggregation_node_config.camera_configs
    @model_validator(mode="after")
    def validate(self   ):
        if set(self.camera_node_configs.keys()) != set(self.aggregation_node_config.camera_configs.keys()):
            raise ValueError("Camera IDs in camera_node_configs and aggregation_node_config.camera_configs must match")
        return self

    @classmethod
    def from_camera_configs(cls, *, camera_configs: CameraConfigs) -> "PipelineConfig":
        camera_node_configs = {}
        for cam_id, cam_config in camera_configs.items():
            calibration_camera_node_config = CalibrationCameraNodeConfig(
                camera_config=cam_config,
                tracker_config=CharucoTrackerConfig(),
                annotator_config=CharucoAnnotatorConfig()
            )
            mocap_camera_node_config = MocapCameraNodeConfig(
                camera_config=cam_config
            )
            camera_node_configs[cam_id] = CameraNodeConfig(
                camera_config=cam_config,
                calibration_camera_node_config=calibration_camera_node_config,
                mocap_camera_node_config=mocap_camera_node_config
            )
        calibration_aggregation_node_config = CalibrationAggregationNodeConfig(
            camera_configs=camera_configs
        )
        mocap_aggregation_node_config = MocapAggregationNodeConfig(
            camera_configs=camera_configs
        )
        aggregation_node_config = AggregationNodeConfig(
            camera_configs=camera_configs,
            calibration_aggregation_node_config=calibration_aggregation_node_config,
            mocap_aggregation_node_config=mocap_aggregation_node_config
        )
        return cls(
            camera_node_configs=camera_node_configs,
            aggregation_node_config=aggregation_node_config
        )


