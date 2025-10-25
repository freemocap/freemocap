from copy import copy

import numpy as np
from numpydantic import NDArray, Shape
from pydantic import BaseModel, ConfigDict
from skellycam.core.types.frontend_payload_bytearray import create_frontend_payload
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.camera_node import CameraNodeImageAnnotater
from freemocap.core.pubsub.pubsub_topics import CameraNodeOutputMessage, AggregationNodeOutputMessage
from freemocap.core.types.type_overloads import FrameNumberInt


class CharucoBoardPayload(BaseModel):
    charuco_corners_in_object_coordinates: NDArray[Shape["* charuco_corners, 3 xyz"], np.float64]
    charuco_ids: NDArray[Shape["* charuco_corners, ..."], np.int32]
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
    frame_number: FrameNumberInt
    camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage]  # TODO - handle mocap stuff too
    aggregation_node_output: AggregationNodeOutputMessage


class UnpackagedFrontendPayload(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    frame_number: FrameNumberInt
    frames: dict[CameraIdString, np.recarray]
    camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage | None]
    aggregation_node_output: AggregationNodeOutputMessage | None = None


    @classmethod
    def from_frame_number(cls, frame_number: FrameNumberInt, frames: dict[CameraIdString, np.recarray]) -> "UnpackagedFrontendPayload":
        return cls(frame_number=frame_number,
                   frames=frames,
                   camera_node_outputs={camera_id: None for camera_id in frames.keys()})

    @classmethod
    def from_camera_node_output(cls,
                                 frames: dict[CameraIdString, np.recarray],
                                 camera_node_output:CameraNodeOutputMessage) -> "UnpackagedFrontendPayload":
        camera_node_outputs:dict[CameraIdString, CameraNodeOutputMessage | None] = {camera_id: None for camera_id in frames.keys()}
        camera_node_outputs[camera_node_output.camera_id] = camera_node_output
        return cls(frame_number=camera_node_output.frame_number,
                     frames=frames,
                   camera_node_outputs=camera_node_outputs)

    @classmethod
    def from_aggregation_node_output(cls,
                                     frames: dict[CameraIdString, np.recarray],
                                     aggregation_node_output: AggregationNodeOutputMessage) -> "UnpackagedFrontendPayload":
        return cls(frame_number=aggregation_node_output.frame_number,
                   frames=frames,
                   camera_node_outputs={camera_id: None for camera_id in frames.keys()},
                   aggregation_node_output=aggregation_node_output)

    def add_camera_node_output(self, camera_node_output: CameraNodeOutputMessage) -> None:
        if camera_node_output.camera_id not in self.camera_node_outputs:
            raise ValueError(
                f"Received unexpected camera ID '{camera_node_output.camera_id}' "
                f"not in expected cameras: {list(self.camera_node_outputs.keys())}"
            )
        if camera_node_output.camera_id not in self.frames:
            raise ValueError(
                f"Camera ID '{camera_node_output.camera_id}' not found in frames: {list(self.frames.keys())}"
            )
        if camera_node_output.frame_number != self.frame_number:
            raise ValueError(
                f"Camera node output frame number {camera_node_output.frame_number} "
                f"does not match payload frame number {self.frame_number}"
            )
        self.camera_node_outputs[camera_node_output.camera_id] = camera_node_output

    def add_aggregation_node_output(self, aggregation_node_output: AggregationNodeOutputMessage) -> None:
        if aggregation_node_output.frame_number != self.frame_number:
            raise ValueError(
                f"Aggregation node output frame number {aggregation_node_output.frame_number} "
                f"does not match payload frame number {self.frame_number}"
            )
        self.aggregation_node_output = aggregation_node_output

    @property
    def camera_ids_matched(self) -> bool:
        if self.frames is None or self.camera_node_outputs is None:
            return False
        return set(self.frames.keys()) == set(self.camera_node_outputs.keys())

    @property
    def all_camera_outputs_received(self) -> bool:
        """Check that all camera node outputs have been received (all values are non-None)."""
        if self.camera_node_outputs is None:
            return False
        return all(output is not None for output in self.camera_node_outputs.values())

    @property
    def ready_to_package(self) -> bool:
        return all([
            self.frames is not None,
            self.camera_node_outputs is not None,
            self.aggregation_node_output is not None,
            self.camera_ids_matched,
            self.all_camera_outputs_received,  # New check
        ])

    def to_frontend_payload(self, annotators:dict[CameraIdString, CameraNodeImageAnnotater]) -> tuple[FrontendPayload, bytes]:
        frontend_payload = FrontendPayload(
            frame_number=self.frame_number,
            camera_node_outputs=self.camera_node_outputs,
            aggregation_node_output=self.aggregation_node_output
        )

        for camera_id, annotator in annotators.items():
            self.frames[camera_id].image[0] = annotator.annotate_image(
                image=self.frames[camera_id].image[0],
                charuco_observation=self.camera_node_outputs[camera_id].charuco_observation)

        return frontend_payload, copy(create_frontend_payload(self.frames))
