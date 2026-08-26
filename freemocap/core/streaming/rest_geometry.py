"""The wire's rest-geometry types: the standard human's segments and landmarks at rest.

FreeMoCap's projection of SkellyForge's SkeletonDefinition + RestPose onto the
self-describing CBOR frame. Pure data (frozen slots) plus to_cbor_message() returning
plain Python types; the streaming layer owns the actual CBOR encoding.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skellyforge.core.math.geometry.orthonormal_basis.spatial_axis import SpatialAxis

_AXIS_NAMES = ("x", "y", "z")


def _signed_axis(axis: SpatialAxis) -> str:
    """The wire's signed axis name ("x"/"-y") for a SpatialAxis."""
    return ("-" if axis.sign < 0 else "") + _AXIS_NAMES[axis.index]


@dataclass(frozen=True, slots=True)
class PrimaryAxis:
    """A segment's primary direction, as a signed axis name ("x"/"-y"/...)."""

    value: str

    @classmethod
    def from_spatial_axis(cls, axis: SpatialAxis) -> "PrimaryAxis":
        return cls(value=_signed_axis(axis))

    def to_cbor_message(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class RestSegment:
    """One segment at rest: name, parent, primary direction, rest orientation, proportion.

    The model is DIMENSIONLESS. `length_proportion` is this segment's length as a fraction
    of body height, so the same model describes a toddler and a basketball player; a
    consumer that wants millimetres multiplies by the instance's `body_height_mm`, or uses
    the per-frame `SEGMENT_LENGTHS` channel where the segment was actually measured.
    """

    name: str
    parent: str | None
    primary_axis: PrimaryAxis
    rest_orientation: tuple[float, float, float, float]  # wxyz
    length_proportion: float
    is_fully_specified: bool = False

    def to_cbor_message(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "parent": self.parent,
            "primary_axis": self.primary_axis.to_cbor_message(),
            "rest_orientation": list(self.rest_orientation),
            "length_proportion": self.length_proportion,
            "is_fully_specified": self.is_fully_specified,
        }


@dataclass(frozen=True, slots=True)
class RestLandmark:
    """One landmark at rest: its name and rest position, as body-height proportions."""

    name: str
    rest_position: tuple[float, float, float] | None = None

    def to_cbor_message(self) -> dict[str, Any]:
        result: dict[str, Any] = {"name": self.name}
        if self.rest_position is not None:
            result["rest_position"] = list(self.rest_position)
        return result
