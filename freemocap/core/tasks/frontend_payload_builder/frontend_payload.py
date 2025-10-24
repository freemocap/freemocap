from typing import Hashable

import numpy as np
from numpydantic import NDArray, Shape
from pydantic import BaseModel
from freemocap.core.types.type_overloads import Point3d, FrameNumberInt
from skellycam.core.types.type_overloads import  MultiframeTimestampFloat


class CharucoBoardPayload(BaseModel):
    charuco_corners_in_object_coordinates: NDArray[Shape["* charuco_corners, 3 xyz"], np.float64]
    charuco_ids: NDArray[Shape["* ch0aruco_corners, ..."], np.int32]
    translation_vector: NDArray[Shape["3 xyz"], np.float64]
    rotation_vector: NDArray[Shape["3 xyz"], np.float64]

    @classmethod
    def create(cls,
               charuco_corners_in_object_coordinates: NDArray[Shape["* charuco_corners, 3 xyz"], np.float64] | None,
               charuco_ids: NDArray[Shape["* charuco_corners, ..."], np.int32] | None,
               translation_vector: NDArray[Shape["3 xyz"], np.float64] | None,
               rotation_vector: NDArray[Shape["3 xyz"], np.float64] | None):
        return cls(
            charuco_corners_in_object_coordinates=charuco_corners_in_object_coordinates.tolist() if charuco_corners_in_object_coordinates is not None else None,
            charuco_ids=charuco_ids.tolist() if charuco_ids is not None else None,
            translation_vector=translation_vector.tolist() if translation_vector is not None else None,
            rotation_vector=rotation_vector.tolist() if rotation_vector is not None else None
            )


class FrontendPayload(BaseModel):
    frame_number:FrameNumberInt
    timestamp: MultiframeTimestampFloat
    images_byte_array: bytes
    points3d: dict[Hashable, Point3d]

