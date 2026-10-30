"""One skeleton's reconstruction for one frame.

The aggregator used to publish the human's reconstruction as a handful of flat fields, one
per quantity. With several skeletons in a frame those would each have to become a dict
keyed by model, in eight places, and nothing would stop them disagreeing about which models
they had. This is the one record instead, and the aggregator publishes a dict of them.

Deliberately dependency-light (numpy only): `pubsub_topics` imports it, and that module is
imported almost everywhere.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping, Iterator
from functools import lru_cache
from skellyforge.core.data_tensors.channel_values import ChannelValues, SPATIAL_COMPONENTS

import numpy as np
from skellyforge.core.skeleton.pose.rigid_body_diagnostics import RigidBodyResidual


@dataclass
class SkeletonReconstruction:
    """What one skeleton looked like this frame, and how big it is.

    Every field is optional in the sense that a frame may not have produced it - nothing
    was visible, the fit has no scale yet, biomechanics is off. Absent means absent; none
    of these is ever filled with zeros to keep a shape.

    Attributes:
        model_id: which skeleton this is, matching a `TrackedSkeletonBundle`.
        mapped_keypoints: mapping observations, keyed by canonical landmark identity.
        landmarks: scaled model-local geometry transformed by its owning solved segment.
        segment_origins: anchor-positioned translations keyed by segment; children attach to
            the parent's rigid landmark. Geometry requires a measured path to the anchor.
        segment_rotations_world: per-segment world quaternions (wxyz).
        segment_rotations_local: per-segment parent-relative quaternions (wxyz).
        segment_lengths: fitted length per segment, in millimetres, for EVERY segment -
            the ones nothing saw are sized by the fitted scale.
        fitted_scale_mm: this skeleton's fitted size in the unit its model names
            (stature for the human, square length for a board). `None` until something
            has measured it, which means "no size", not "assume a default".
        joint_angles: named joint angles in radians, for skeletons that have joints.
        reprojected_segment_origins: camera id -> segment name -> (x, y) in capture pixels.
        center_of_mass: this skeleton's whole-body centre of mass.
        extrapolated_center_of_mass: its XCoM, for skeletons that opted into it.
    """

    model_id: str
    rigid_body_residuals: Mapping[str, RigidBodyResidual] = field(default_factory=dict)
    mapped_keypoints: Mapping[str, np.ndarray] = field(default_factory=dict)
    segment_origins: Mapping[str, np.ndarray] = field(default_factory=dict)
    landmarks: Mapping[str, np.ndarray] = field(default_factory=dict)
    segment_rotations_world: Mapping[str, np.ndarray] = field(default_factory=dict)
    segment_rotations_local: Mapping[str, np.ndarray] = field(default_factory=dict)
    segment_lengths: Mapping[str, float] = field(default_factory=dict)
    fitted_scale_mm: float | None = None
    joint_angles: Mapping[str, tuple[float, ...] | np.ndarray] | None = None
    reprojected_segment_origins: dict[str, Mapping[str, tuple[float, float] | np.ndarray]] = field(
        default_factory=dict
    )
    center_of_mass: np.ndarray | None = None
    extrapolated_center_of_mass: np.ndarray | None = None

    def __post_init__(self) -> None:
        for field_name, components in (
            ('mapped_keypoints', SPATIAL_COMPONENTS), ('landmarks', SPATIAL_COMPONENTS),
            ('segment_origins', SPATIAL_COMPONENTS),
            ('segment_rotations_world', ('w', 'x', 'y', 'z')),
            ('segment_rotations_local', ('w', 'x', 'y', 'z')), ('segment_lengths', ())):
            setattr(self, field_name, ChannelValues.from_mapping(getattr(self, field_name), component_names=components))


class ResidualValues(Mapping):
    """Dense residual data; individual records materialize only at named/JSON access."""
    def __init__(self, *, names: tuple[str, ...], measured: np.ndarray, reference: np.ndarray, residual: np.ndarray, reference_kind: str) -> None:
        self.channel_values = ChannelValues(names, np.stack((measured, reference, residual), axis=-1),
            component_names=('measured_length', 'reference_length', 'residual')).immutable_copy()
        self.reference_kind = reference_kind

    def __len__(self) -> int:
        return len(self.channel_values)

    def __iter__(self) -> Iterator[str]:
        return iter(self.channel_values)

    def __getitem__(self, name: str) -> RigidBodyResidual:
        values = self.channel_values[name]
        return RigidBodyResidual(*(float(value) if np.isfinite(value) else None for value in values), self.reference_kind)


class JointValues(Mapping):
    """Declared joint slices over a single flat angle channel, without padded widths."""
    def __init__(self, *, angle_values: ChannelValues, definitions: tuple) -> None:
        self.angle_values = angle_values
        self.names, self.offsets, self.indices, expected = _joint_selection(definitions)
        if angle_values.names != expected:
            raise ValueError("Angle values must follow declared joint/component ordering")
        self.present = np.add.reduceat(angle_values.entry_present.astype(np.int64), self.offsets[:-1]) == np.diff(self.offsets)

    def __len__(self) -> int:
        return int(self.present.sum())

    def __iter__(self) -> Iterator[str]:
        return (self.names[index] for index in np.flatnonzero(self.present))

    def __getitem__(self, name: str) -> np.ndarray:
        index = self.indices[name]
        if not self.present[index]:
            raise KeyError(name)
        return self.angle_values.data_values[self.offsets[index]:self.offsets[index + 1], 0]


@lru_cache(maxsize=32)
def _joint_selection(definitions):
    names = tuple(name for name, _ in definitions)
    counts = np.array([len(components) for _, components in definitions], np.int64)
    if not len(counts) or np.any(counts <= 0):
        raise ValueError("Joint slices require nonempty declared components")
    return names, np.concatenate(([0], np.cumsum(counts))), {name: i for i, name in enumerate(names)}, tuple(name for _, components in definitions for name in components)
