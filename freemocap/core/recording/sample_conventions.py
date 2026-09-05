"""Named scalar components and units at the recording serialization boundary."""

from enum import StrEnum


class SampleComponent(StrEnum):
    LENGTH = "length"
    SCALE = "scale"
    RADIANS = "radians"
    W = "w"
    X = "x"
    Y = "y"
    Z = "z"
    VISIBILITY = "visibility"
    TIMESTAMP = "timestamp_s"


class SampleUnit(StrEnum):
    RADIANS = "rad"
    PIXELS = "px"
    DIMENSIONLESS = "1"
    SECONDS = "s"
    MILLIMETERS = "mm"


class TimingSampleName(StrEnum):
    CAPTURE = "capture"
    SYNCHRONIZED = "synchronized"
