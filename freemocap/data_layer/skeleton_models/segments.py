from typing import Dict
from pydantic import BaseModel, model_validator

from freemocap.data_layer.skeleton_models.marker_info import MarkerInfo


class Segment(BaseModel):
    proximal: str
    distal: str


class SegmentAnthropometry(BaseModel):
    segment_com_length: float
    segment_com_percentage: float


class Segments(BaseModel):
    markers: MarkerInfo
    segment_connections: Dict[str, Segment]

    @model_validator(mode="before")
    def check_that_all_markers_exist(cls, values):
        markers = values.get("markers").all_markers
        segment_connections = values.get("segment_connections")

        for segment_name, segment_connection in segment_connections.items():
            if segment_connection.get("proximal") not in markers:
                raise ValueError(
                    f"The proximal marker {segment_connection.proximal} for {segment_name} is not in the list of markers or virtual markers."
                )
            if segment_connection.get("distal") not in markers:
                raise ValueError(
                    f"The distal marker {segment_connection.distal} for {segment_name} is not in the list of markers or virtual markers."
                )

        return values
