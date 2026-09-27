"""Adapt explicitly selected direct mappings to Forge's connected-fit targets.

This is preparation for connected fitting, not a production reconstruction stage.
Mapping definitions and model attachments remain owned by the supplied bundle.
"""

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellyforge.core.skeleton.pose.fit_connected_pose import LandmarkTarget

from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle


@dataclass(frozen=True)
class ConnectedFitObservations:
    targets: dict[str, LandmarkTarget]
    source_keypoints: dict[str, str]
    """Selected landmark -> source, including selections missing in this frame."""


def connected_fit_observations(
    *,
    bundle: TrackedSkeletonBundle,
    keypoints: Mapping[str, NDArray[np.float64]],
    landmark_tolerances: Mapping[str, float],
) -> ConnectedFitObservations:
    """Prepare direct targets without selecting correspondences or weights implicitly.

    Tolerances are positive modeling scales in the input coordinate units, not
    calibrated measurement uncertainty. Means and offsets are deliberately not
    accepted as independent targets. This does not alter their existing mapping
    or scale-fitting use. Duplicate sources fail even when absent this frame.

    Absent/NaN observations yield no target; infinity or malformed points fail.
    Empty targets are allowed here (a frame can be unobserved); the caller must
    handle that before invoking a fitter requiring observations. No coordinates
    are transformed, filtered or replaced, and target arrays own their storage.
    """
    direct: dict[str, str] = {}
    for snapshot in bundle.landmark_mapping.mapping_snapshots():
        prefix = snapshot.prefix or ""
        if snapshot.passthrough:
            entries = {
                name.removeprefix(prefix): name
                for name in snapshot.known_tracker_keypoints or ()
            }
        else:
            entries = {
                name: prefix + entry
                for name, entry in snapshot.entries.items()
                if isinstance(entry, str)
            }
        for name, source in entries.items():
            if name in direct:
                raise ValueError(f"Multiple direct mappings for landmark {name!r}")
            direct[name] = source

    sources: dict[str, str] = {}
    used: dict[str, str] = {}
    for name, tolerance in landmark_tolerances.items():
        if name not in bundle.skeleton.landmarks:
            raise ValueError(f"Unknown model landmark {name!r}")
        if name not in direct:
            raise ValueError(f"Landmark {name!r} requires a direct keypoint mapping")
        if not np.isfinite(tolerance) or tolerance <= 0:
            raise ValueError(
                f"Target tolerance for {name!r} must be finite and positive"
            )
        source = direct[name]
        if source not in bundle.tracker_keypoint_names:
            raise ValueError(f"Undeclared tracker keypoint {source!r}")
        if source in used:
            raise ValueError(
                f"Landmarks {used[source]!r} and {name!r} reuse keypoint {source!r}"
            )
        used[source] = name
        sources[name] = source

    targets: dict[str, LandmarkTarget] = {}
    for name, source in sources.items():
        if source not in keypoints:
            continue
        position = np.asarray(keypoints[source], dtype=np.float64)
        if position.shape != (3,) or np.isinf(position).any():
            raise ValueError(
                f"Keypoint {source!r} must be an XYZ point without infinity"
            )
        if np.isnan(position).any():
            continue
        targets[name] = LandmarkTarget(
            position=Point.from_array(values=position.copy()),
            tolerance=float(landmark_tolerances[name]),
        )
    return ConnectedFitObservations(targets=targets, source_keypoints=sources)
