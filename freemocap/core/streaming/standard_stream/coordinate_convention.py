"""Coordinate-convention value type for the standard stream.

Convention is a *schema* fact — declared once, never per sample. See
[07 — Coordinate Conventions](docs/streaming-compatibility/07-coordinate-conventions.md).
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


# FreeMoCap's canonical convention: robotics/biomechanics standards — millimeters,
# right-handed, +Z up. ``forward_axis`` is the one open TBD (see
# [07 — Coordinate Conventions](docs/streaming-compatibility/07-coordinate-conventions.md)):
# +Y is the working assumption (the Blender export path treats data as X-right /
# Y-forward / Z-up) pending confirmation against the ground-plane calibration basis.
FREEMOCAP_CANONICAL_CONVENTION = CoordinateConvention(
    units=Units.MILLIMETERS,
    handedness=Handedness.RIGHT,
    up_axis=Axis.PLUS_Z,
    forward_axis=Axis.PLUS_Y,  # TODO(convention): confirm the canonical forward-axis
    rotation_frame=RotationFrame.LOCAL,
    rotation_form=RotationForm.QUATERNION,
)
