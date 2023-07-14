import pprint
from typing import List, Dict, Tuple
from typing import Optional, Any

from pydantic import BaseModel, Field, root_validator

from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.data_models.mediapipe_skeleton_names_and_connections import (
    mediapipe_skeleton_schema,
)


class Point(BaseModel):
    """
    A point in 3D space at a particular time
    """

    x: Optional[float] = Field(None, description="The X-coordinate of the point")
    y: Optional[float] = Field(None, description="The Y-coordinate of the point")
    z: Optional[float] = Field(None, description="The Z-coordinate of the point")


class VirtualMarkerDefinition(BaseModel):
    """
    A virtual marker, defined by combining multiple markers with weights to generate a new marker/point
    """

    marker_names: List[str] = Field(
        default_factory=list, description="The names of the markers that define this virtual marker"
    )
    marker_weights: List[float] = Field(
        default_factory=list, description="The weights of the markers that define this virtual marker, must sum to 1"
    )

    @root_validator
    def check_weights(cls, values):
        marker_weights = values.get("marker_weights")
        if sum(marker_weights) != 1:
            raise ValueError(f"Marker weights must sum to 1, got {marker_weights}")
        return values


class SegmentSchema(BaseModel):
    """
    A schema for a segment of a skeleton, defined by a set of tracked points and connections between them
    """

    point_names: List[str] = Field(
        default_factory=list, description="The names of the tracked points that define this segment"
    )
    virtual_marker_definitions: Optional[Dict[str, VirtualMarkerDefinition]] = Field(
        default_factory=dict, description="The virtual markers that define this segment"
    )
    connections: List[Tuple[int, int]] = Field(
        default_factory=list, description="The connections between the tracked points"
    )
    parent: Optional[str] = Field(None, description="The name of the parent of this segment")


class SkeletonSchema(BaseModel):
    body: SegmentSchema = Field(default_factory=SegmentSchema, description="The tracked points that define the body")
    hands: Dict[str, SegmentSchema] = Field(
        default_factory=dict, description="The tracked points that define the hands: keys - (left, right)"
    )
    face: SegmentSchema = Field(default_factory=SegmentSchema, description="The tracked points that define the face")

    def __init__(self, schema_dict: Dict[str, Dict[str, Any]]):
        super().__init__()
        self.body = SegmentSchema(**schema_dict["body"])
        self.hands = {hand: SegmentSchema(**hand_schema) for hand, hand_schema in schema_dict["hands"].items()}
        self.face = SegmentSchema(**schema_dict["face"])

    def dict(self):
        d = {}
        d["body"] = self.body.dict()
        d["hands"] = {hand: hand_schema.dict() for hand, hand_schema in self.hands.items()}
        d["face"] = self.face.dict()
        return d


class Timestamps(BaseModel):
    # TODO - Add Unix time and ISO format stuff and whatnot
    mean: Optional[float] = Field(None, description="The mean timestamp for this frame")
    by_camera: Dict[str, Any] = Field(
        default_factory=dict, description="Timestamps for each camera on this frame (key is video name)"
    )


class FrameData(BaseModel):
    """
    The data for a single frame
    """

    timestamps: Timestamps = Field(default_factory=Timestamps, description="Timestamp data")
    tracked_points: Dict[str, Point] = Field(default_factory=dict, description="The points being tracked")

    @property
    def tracked_point_names(self):
        return list(self.tracked_points.keys())

    @property
    def timestamp(self):
        return self.timestamps.mean

    def to_dict(self):
        d = {}
        d["timestamps"] = self.timestamps.dict()
        d["tracked_points"] = {name: point.dict() for name, point in self.tracked_points.items()}
        return d


class InfoDict(BaseModel):
    """
    A dictionary of information about this recording, such as the measured segement lengths and the schemas that we can use to interpret the tracked points (i.e./e.g. how to connect the dots of skeleton)
    """

    segment_lengths: Dict[str, Any] = Field(default_factory=dict, description="The lengths of the segments of the body")
    schemas: List[BaseModel] = Field(default_factory=list, description="The schemas for the tracked points")


if __name__ == "__main__":
    # nested_dict = create_nested_dict(FramePacket)
    # print(json.dumps(nested_dict, indent=4))

    print("=====================================\n\n===============================")

    skeleton_schema = SkeletonSchema(schema_dict=mediapipe_skeleton_schema)

    pprint.pp(skeleton_schema.dict())
