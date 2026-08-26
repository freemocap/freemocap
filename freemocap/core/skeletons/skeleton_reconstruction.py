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

import numpy as np


@dataclass
class SkeletonReconstruction:
    """What one skeleton looked like this frame, and how big it is.

    Every field is optional in the sense that a frame may not have produced it - nothing
    was visible, the fit has no scale yet, biomechanics is off. Absent means absent; none
    of these is ever filled with zeros to keep a shape.

    Attributes:
        model_id: which skeleton this is, matching a `TrackedSkeletonBundle`.
        landmarks: hydrated landmark world positions, including segment origins.
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
    landmarks: dict[str, np.ndarray] = field(default_factory=dict)
    segment_rotations_world: dict[str, np.ndarray] = field(default_factory=dict)
    segment_rotations_local: dict[str, np.ndarray] = field(default_factory=dict)
    segment_lengths: dict[str, float] = field(default_factory=dict)
    fitted_scale_mm: float | None = None
    joint_angles: dict[str, tuple[float, float, float]] | None = None
    reprojected_segment_origins: dict[str, dict[str, tuple[float, float]]] = field(
        default_factory=dict
    )
    center_of_mass: np.ndarray | None = None
    extrapolated_center_of_mass: np.ndarray | None = None
