import logging

import numpy as np
from pydantic import BaseModel
from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseTracker, BaseObservation
from skellytracker.trackers.charuco_tracker import CharucoTracker

from freemocap.core.pipeline.pipeline_configs import CameraNodeTaskConfig, CalibrationCameraNodeConfig
from freemocap.core.types.type_overloads import FrameNumberInt

logger = logging.getLogger(__name__)


class BaseCameraNodeTask(BaseModel):
    config: CameraNodeTaskConfig
    tracker: BaseTracker

    @property
    def camera_id(self) -> CameraIdString:
        return self.camera_config.camera_id

    @property
    def camera_config(self) -> CameraConfig:
        return self.config.camera_config

class CalibrationCameraNodeTask(BaseCameraNodeTask):
    config: CalibrationCameraNodeConfig
    tracker: CharucoTracker

    @classmethod
    def create(cls, *,
               config: CalibrationCameraNodeConfig):
        return cls(
            config=config,
            tracker=CharucoTracker.create(config=config.tracker_config)
        )

    def process_image(self,
                      frame_number:FrameNumberInt,
                      image:np.ndarray) ->BaseObservation:
        return self.tracker.process_image(frame_number=frame_number,image=image)
