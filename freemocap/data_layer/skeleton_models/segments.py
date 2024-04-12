from typing import Dict
from pydantic import BaseModel, root_validator

from freemocap.data_layer.skeleton_models.marker_info import MarkerInfo


class Segment(BaseModel):
    proximal: str
    distal: str


class Segments(BaseModel):
    markers: MarkerInfo
    segment_connections: Dict[str, Segment]

    @root_validator
    def check_that_all_markers_exist(cls, values):
        markers = values.get("markers").all_markers
        segment_connections = values.get("segment_connections")

        for segment_name, segment_connection in segment_connections.items():
            if segment_connection.proximal not in markers:
                raise ValueError(
                    f"The proximal marker {segment_connection.proximal} for {segment_name} is not in the list of markers or virtual markers."
                )
            if segment_connection.distal not in markers:
                raise ValueError(
                    f"The distal marker {segment_connection.distal} for {segment_name} is not in the list of markers or virtual markers."
                )

        return values
