import numpy as np
from freemocap.pipelines.pipeline_abcs import BasePipelineOutputData
from pydantic import BaseModel
from skellycam.core.frames.payloads.frontend_image_payload import FrontendFramePayload

from freemocap.pipelines.calibration_pipeline.calibration_aggregation_node import CalibrationPipelineOutputData
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload


class CharucoBoardPayload(BaseModel):
    charuco_corners_in_object_coordinates: list[list[float]]
    charuco_ids: list[int]
    translation_vector: list[float]
    rotation_vector: list[float]

    @classmethod
    def create(cls,
               charuco_corners_in_object_coordinates: np.ndarray | None,
               charuco_ids: np.ndarray[int] | None,
               translation_vector: np.ndarray[float] | None,
               rotation_vector: np.ndarray[float] | None):
        return cls(
            charuco_corners_in_object_coordinates=charuco_corners_in_object_coordinates.tolist() if charuco_corners_in_object_coordinates is not None else None,
            charuco_ids=charuco_ids.tolist() if charuco_ids is not None else None,
            translation_vector=translation_vector.tolist() if translation_vector is not None else None,
            rotation_vector=rotation_vector.tolist() if rotation_vector is not None else None
            )


class FreemocapFrontendPayload(FrontendFramePayload):
    latest_pipeline_output: dict[str, object] | None
    points3d: dict[str, tuple] | None

    @classmethod
    def create(cls,
               multi_frame_payload: MultiFramePayload,
               latest_pipeline_output: BasePipelineOutputData | None = None):

        latest_pipeline_output_dict = latest_pipeline_output.model_dump() if latest_pipeline_output is not None else {"hi": "wowww"}

        return cls(
            **FrontendFramePayload.from_multi_frame_payload(multi_frame_payload).model_dump(),
            latest_pipeline_output=latest_pipeline_output_dict,
            points3d=latest_pipeline_output.aggregation_layer_output.points3d if latest_pipeline_output is not None else None
        )
