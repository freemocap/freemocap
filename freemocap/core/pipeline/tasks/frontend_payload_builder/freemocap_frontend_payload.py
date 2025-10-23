from typing import Hashable

import numpy as np
from numpydantic import NDArray, Shape
from pydantic import BaseModel
from skellycam import CameraId
from skellycam.core.frames.payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload

from freemocap.core.pipeline.processing_pipeline import BasePipelineOutputData


class CharucoBoardPayload(BaseModel):
    charuco_corners_in_object_coordinates: NDArray[Shape["* charuco_corners, 3 xyz"], np.float64]
    charuco_ids: NDArray[Shape["* ch0aruco_corners, ..."], np.int32]
    translation_vector: NDArray[Shape["3 xyz"], np.float64]
    rotation_vector: NDArray[Shape["3 xyz"], np.float64]

    @classmethod
    def create(cls,
               charuco_corners_in_object_coordinates: NDArray[Shape["* charuco_corners, 3 xyz"], np.float64] | None,
               charuco_ids: NDArray[Shape["* ch0aruco_corners, ..."], np.int32] | None,
               translation_vector: NDArray[Shape["3 xyz"], np.float64] | None,
               rotation_vector: NDArray[Shape["3 xyz"], np.float64] | None):
        return cls(
            charuco_corners_in_object_coordinates=charuco_corners_in_object_coordinates.tolist() if charuco_corners_in_object_coordinates is not None else None,
            charuco_ids=charuco_ids.tolist() if charuco_ids is not None else None,
            translation_vector=translation_vector.tolist() if translation_vector is not None else None,
            rotation_vector=rotation_vector.tolist() if rotation_vector is not None else None
            )


class FreemocapFrontendPayload(FrontendFramePayload):
    latest_pipeline_output: BasePipelineOutputData | None
    points3d: dict[Hashable, NDArray[Shape["3 xyz"], np.float64]] | None


    @classmethod
    def create(cls,
               multi_frame_payload: MultiFramePayload,
               latest_pipeline_output: BasePipelineOutputData | None = None):

        return cls(
            **FrontendFramePayload.from_multi_frame_payload(multi_frame_payload).model_dump(),
            latest_pipeline_output=latest_pipeline_output,
            points3d=latest_pipeline_output.aggregation_layer_output.points3d if latest_pipeline_output is not None else None
        )
