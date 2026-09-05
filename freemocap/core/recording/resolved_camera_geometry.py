"""Serializable camera geometry without calibration acquisition or solver state."""

from enum import StrEnum

import numpy as np
from pydantic import BaseModel, ConfigDict

from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics


class CalibrationBasis(StrEnum):
    FREEMOCAP = "freemocap_x_forward_y_left_z_up"


class ResolvedCameraGeometry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    camera_id: str
    camera_index: int
    image_size: tuple[int, int]
    intrinsics: CameraIntrinsics
    world_to_camera_wxyz: tuple[float, float, float, float]
    world_to_camera_translation_mm: tuple[float, float, float]
    basis: CalibrationBasis = CalibrationBasis.FREEMOCAP

    @classmethod
    def from_camera(cls, camera: CameraModel) -> "ResolvedCameraGeometry":
        return cls(
            camera_id=camera.id,
            camera_index=camera.index,
            image_size=camera.image_size,
            intrinsics=camera.intrinsics.model_copy(deep=True),
            world_to_camera_wxyz=tuple(camera.extrinsics.quaternion_wxyz),
            world_to_camera_translation_mm=tuple(camera.extrinsics.translation),
        )

    def to_camera(self) -> CameraModel:
        extrinsics = CameraExtrinsics(
            quaternion_wxyz=np.array(self.world_to_camera_wxyz),
            translation=np.array(self.world_to_camera_translation_mm),
        )
        return CameraModel(
            id=self.camera_id,
            index=self.camera_index,
            image_size=self.image_size,
            intrinsics=self.intrinsics.model_copy(deep=True),
            extrinsics=extrinsics,
            world_position=extrinsics.world_position,
            world_orientation=extrinsics.world_orientation,
        )
