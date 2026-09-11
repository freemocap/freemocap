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
    # Bounding-box corners, plus the detector's score and whether the detector actually
    # ran on this frame (1.0) or the box was carried forward from keypoints (0.0).
    X1 = "x1"
    Y1 = "y1"
    X2 = "x2"
    Y2 = "y2"
    CONFIDENCE = "confidence"
    DETECTOR_RAN = "detector_ran"


class SampleUnit(StrEnum):
    RADIANS = "rad"
    PIXELS = "px"
    DIMENSIONLESS = "1"
    SECONDS = "s"
    MILLIMETERS = "mm"


class TimingSampleName(StrEnum):
    CAPTURE = "capture"
    SYNCHRONIZED = "synchronized"
