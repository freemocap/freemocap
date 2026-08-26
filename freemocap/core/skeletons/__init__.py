"""The skeletons this app tracks, each bundled with what reconstructs it.

A session tracks several — a person and a charuco board are two — so every stage that once
held "the standard human" holds a tuple of `TrackedSkeletonBundle` and loops.
"""
from freemocap.core.skeletons.tracked_skeleton_bundle import (
    KeypointToLandmarkMapping,
    TrackedSkeletonBundle,
)
from freemocap.core.skeletons.standard_human_skeleton import (
    BODY_HEIGHT_SCALE_REFERENCE,
    STANDARD_HUMAN_MODEL_ID,
    build_standard_human_bundle,
)

__all__ = [
    "BODY_HEIGHT_SCALE_REFERENCE",
    "KeypointToLandmarkMapping",
    "STANDARD_HUMAN_MODEL_ID",
    "TrackedSkeletonBundle",
    "build_standard_human_bundle",
]
