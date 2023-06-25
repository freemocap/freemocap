from ctypes import Union
from typing import Optional, Dict, Any, get_origin, get_args

from pydantic import BaseModel, Field

class Point(BaseModel):
    x: Optional[float] = Field(None, description="The X-coordinate of the point")
    y: Optional[float] = Field(None, description="The Y-coordinate of the point")
    z: Optional[float] = Field(None, description="The Z-coordinate of the point")

class Timestamps(BaseModel):
    mean: Optional[float] = Field(None, description="The mean timestamp for this frame")
    per_camera: Dict[str, Any] = Field(default_factory=dict, description="Timestamps for each camera on this frame (key is video name)")

class CenterOfMassData(BaseModel):
    full_body_com: Point = Field(default_factory=Point, description="The center of mass of the full body based on Winter 1995 anthropometric tables")
    segment_coms: Dict[str, Point] = Field(default_factory=dict, description="The center of mass of each body segment")

class FrameData(BaseModel):
    center_of_mass: CenterOfMassData = Field(default_factory=CenterOfMassData, description="The center of mass data")
    body: Dict[str, Point] = Field(default_factory=dict, description="Points representing body landmarks")
    hands: Dict[str, Dict[str, Point]] = Field(default_factory=dict, description="Points representing hand landmarks for both hands (left and right)")
    face: Dict[str, Point] = Field(default_factory=dict, description="Points representing facial landmarks")

class FramePacket(BaseModel):
    timestamps: Timestamps = Field(default_factory=Timestamps, description="Timestamp data")
    data: FrameData = Field(default_factory=FrameData, description="Landmark data for the frame")

class InfoDict(BaseModel):
    segment_lengths: Dict[str, Any] = Field(default_factory=dict, description="The lengths of the segments of the body")
    names_and_connections: Dict[str, Any] = Field(default_factory=dict, description="The names and connections of the body landmarks")


from typing import get_args, get_origin
from pydantic import BaseModel, Field
from typing import Union

def print_model(model, indent=0):
    print("  " * indent + model.__name__)
    for name, field in model.__annotations__.items():
        origin = get_origin(field)
        args = get_args(field)

        if origin is not None:
            # for Optional[X], origin is Union and args is (X, type(None))
            if origin is Union:
                non_optional_args = [a for a in args if a is not type(None)]
                if non_optional_args:
                    field = non_optional_args[0]

        if isinstance(field, type) and issubclass(field, BaseModel):
            print_model(field, indent + 1)
        else:
            description = model.__fields__[name].field_info.description
            print("  " * (indent + 1) + f"{name} ({field}): {description}")

print_model(FramePacket)


if __name__ == "__main__":
    print_model(FramePacket)
