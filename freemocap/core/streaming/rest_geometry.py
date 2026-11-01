"""The wire's rest-geometry types: the standard human's segments and landmarks at rest.

FreeMoCap's projection of SkellyForge's SkeletonDefinition + RestPose onto the
self-describing CBOR frame. Pure data (frozen slots) plus to_cbor_message() returning
plain Python types; the streaming layer owns the actual CBOR encoding.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
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
    consumer that wants millimetres multiplies by the instance's `fitted_scale_mm`, or uses
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
class ModelLandmarkGroup:
    """A named set of a model's landmarks, with its colour already resolved.

    The model carries TAGS and skellyforge's palette turns them into a colour; that
    resolution happens here, on the way to the wire, so a client never needs the palette
    and swapping the palette recolours every client at once.
    """

    name: str
    landmark_names: tuple[str, ...]
    color: str

    def to_cbor_message(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "landmark_names": list(self.landmark_names),
            "color": self.color,
        }


@dataclass(frozen=True, slots=True)
class ModelConnectionGroup:
    """A named set of landmark edges a client should draw, with its colour resolved.

    Distinct from `ModelDefinition.connections`, which joins SEGMENT origins along the
    joint tree. These join landmarks — the only kind of edge a one-segment model has.
    """

    name: str
    pairs: tuple[tuple[str, str], ...]
    color: str

    def to_cbor_message(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "pairs": [list(pair) for pair in self.pairs],
            "color": self.color,
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


@dataclass(frozen=True, slots=True)
class ModelAttachedLines:
    """Prepared local endpoint pairs; static data, never a dynamic channel."""
    segment: str
    authored_length: float
    positions: tuple[float, ...]
    material: dict[str, Any] | None = None
    surfaces: tuple[dict[str, Any], ...] = ()

    def to_cbor_message(self) -> dict[str, Any]:
        return {'segment': self.segment, 'authored_length': self.authored_length, 'positions': list(self.positions),
                **({'material': self.material} if self.material is not None else {}),
                **({'surfaces': list(self.surfaces)} if self.surfaces else {})}

    @classmethod
    def from_attached_lines(cls, item):
        return cls(segment=item.segment, authored_length=item.authored_length, positions=item.positions,
                   material=asdict(item.material) if item.material is not None else None,
                   surfaces=tuple({'positions': list(surface.positions), 'indices': list(surface.indices),
                       'material': asdict(surface.material), 'double_sided': surface.double_sided}
                       for surface in item.surfaces))


@dataclass(frozen=True, slots=True)
class ModelPresentation:
    attached_lines: tuple[ModelAttachedLines, ...]
    excluded_origin_edges: tuple[tuple[str, str], ...]
    excluded_bones: tuple[str, ...]
    connection_materials: tuple[dict[str, Any], ...] = ()

    def to_cbor_message(self) -> dict[str, Any]:
        return {'attached_lines': [item.to_cbor_message() for item in self.attached_lines],
                'excluded_origin_edges': [list(edge) for edge in self.excluded_origin_edges],
                'excluded_bones': list(self.excluded_bones),
                **({'connection_materials': list(self.connection_materials)} if self.connection_materials else {})}
