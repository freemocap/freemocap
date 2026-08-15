"""Coordinate-convention value type for the standard stream.

Convention is a *schema* fact — declared once, never per sample. See
[current-work-plans/00-foundation/conventions.md](../../../current-work-plans/00-foundation/conventions.md).
"""
from __future__ import annotations

import enum

import msgspec


class Units(str, enum.Enum):
    MILLIMETERS = "mm"
    CENTIMETERS = "cm"
    METERS = "m"


class Handedness(str, enum.Enum):
    RIGHT = "right"
    LEFT = "left"


class Axis(str, enum.Enum):
    PLUS_X = "+x"
    MINUS_X = "-x"
    PLUS_Y = "+y"
    MINUS_Y = "-y"
    PLUS_Z = "+z"
    MINUS_Z = "-z"


class RotationFrame(str, enum.Enum):
    LOCAL = "local"  # each bone's rotation is relative to its parent
    WORLD = "world"


class RotationForm(str, enum.Enum):
    QUATERNION = "quaternion"
    EULER = "euler"


class CoordinateConvention(msgspec.Struct, frozen=True):
    """The (units, handedness, up/forward axis, rotation frame+form) of a space."""

    units: Units
    handedness: Handedness
    up_axis: Axis
    forward_axis: Axis
    rotation_frame: RotationFrame
    rotation_form: RotationForm


# FreeMoCap's coordinate convention: robotics/biomechanics standards —
# millimeters, right-handed, +Z up, +X forward (see
# [current-work-plans/00-foundation/conventions.md](../../../current-work-plans/00-foundation/conventions.md)).
# The +X forward value is a **declared internal standard**, not derived from
# whatever the calibration produced — all FreeMoCap data is in it internally,
# conversion happens at the adapter edge on request.
FREEMOCAP_COORDINATE_CONVENTION = CoordinateConvention(
    units=Units.MILLIMETERS,
    handedness=Handedness.RIGHT,
    up_axis=Axis.PLUS_Z,
    forward_axis=Axis.PLUS_X,
    rotation_frame=RotationFrame.LOCAL,
    rotation_form=RotationForm.QUATERNION,
)
