from pydantic import BaseModel, Field
from typing import Dict


class SegmentAnthropometry(BaseModel):
    segment_com_length: float
    segment_com_percentage: float


class CenterOfMassDefinitions(BaseModel):
    center_of_mass_definitions: Dict[str, SegmentAnthropometry] = Field(...)
    # TODO: can add validation to check that segments exist in the segment_connections
