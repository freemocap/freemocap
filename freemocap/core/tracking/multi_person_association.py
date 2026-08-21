"""Small, dependency-light identity features for two-person camera association.

The temporal tracker in SkellyTracker owns per-camera track continuity. This
module associates those stable camera tracks across views using features that
survive a crossing better than bounding boxes alone: pelvis position, relative
bone lengths, and a coarse colour histogram.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class PersonDescriptor:
    detection_id: str
    pelvis: NDArray[np.float64]
    bone_signature: NDArray[np.float64]
    appearance_histogram: NDArray[np.float64]


def appearance_histogram(image: NDArray[np.uint8], bbox: tuple[int, int, int, int]) -> NDArray[np.float64]:
    """Return a normalized 8x8x8 RGB histogram for an in-frame person crop."""
    x1, y1, x2, y2 = bbox
    crop = image[max(0, y1):max(0, y2), max(0, x1):max(0, x2)]
    if crop.size == 0:
        return np.zeros(512, dtype=np.float64)
    histogram, _ = np.histogramdd(
        crop.reshape(-1, 3), bins=(8, 8, 8), range=((0, 256), (0, 256), (0, 256))
    )
    flat = histogram.reshape(-1).astype(np.float64)
    return flat / max(float(flat.sum()), 1.0)


def bone_length_signature(
    points: dict[str, NDArray[np.float64]],
) -> NDArray[np.float64]:
    pairs = (
        ("left_shoulder", "right_shoulder"),
        ("left_hip", "right_hip"),
        ("left_shoulder", "left_wrist"),
        ("right_shoulder", "right_wrist"),
        ("left_hip", "left_ankle"),
        ("right_hip", "right_ankle"),
    )
    lengths = [
        float(np.linalg.norm(points[a] - points[b])) if a in points and b in points else np.nan
        for a, b in pairs
    ]
    signature = np.asarray(lengths, dtype=np.float64)
    finite = signature[np.isfinite(signature)]
    scale = float(np.median(finite)) if finite.size else 1.0
    return np.nan_to_num(signature / max(scale, 1e-6), nan=0.0)


def descriptor_cost(reference: PersonDescriptor, candidate: PersonDescriptor) -> float:
    pelvis_cost = min(float(np.linalg.norm(reference.pelvis - candidate.pelvis)) / 2_000.0, 1.0)
    signature_cost = min(
        float(np.linalg.norm(reference.bone_signature - candidate.bone_signature))
        / max(np.sqrt(reference.bone_signature.size), 1.0),
        1.0,
    )
    overlap = float(np.sqrt(reference.appearance_histogram * candidate.appearance_histogram).sum())
    appearance_cost = 1.0 - min(max(overlap, 0.0), 1.0)
    return 0.45 * pelvis_cost + 0.35 * signature_cost + 0.20 * appearance_cost


def associate_two_person_views(
    references: list[PersonDescriptor],
    candidates: list[PersonDescriptor],
    *,
    max_cost: float = 0.75,
    ambiguity_margin: float = 0.06,
) -> dict[str, str]:
    """Map reference ids to candidate ids, holding ambiguous matches.

    The exhaustive assignment is intentional: the milestone is capped at two
    people, making this deterministic equivalent of Hungarian assignment easy
    to audit while avoiding another runtime dependency in the realtime path.
    """
    refs = references[:2]
    detections = candidates[:2]
    if not refs or not detections:
        return {}
    cost = np.asarray(
        [[descriptor_cost(reference, candidate) for candidate in detections] for reference in refs]
    )
    assignments = []
    for candidate_order in permutations(range(len(detections)), min(len(refs), len(detections))):
        pairs = list(zip(range(len(candidate_order)), candidate_order, strict=False))
        assignments.append((sum(float(cost[row, column]) for row, column in pairs), pairs))
    _, best = min(assignments, key=lambda item: item[0])
    result: dict[str, str] = {}
    for row, column in best:
        alternatives = np.delete(cost[row], column)
        ambiguous = alternatives.size and float(alternatives.min() - cost[row, column]) < ambiguity_margin
        if not ambiguous and cost[row, column] <= max_cost:
            result[refs[row].detection_id] = detections[column].detection_id
    return result


def performer_parquet_rows(
    frame_number: int,
    performer_points: dict[str, dict[str, NDArray[np.float64]]],
) -> list[dict[str, float | int | str]]:
    """Long-form rows with performer_id for Parquet writers."""
    rows: list[dict[str, float | int | str]] = []
    for performer_id, points in performer_points.items():
        for point_name, point in points.items():
            xyz = np.asarray(point, dtype=np.float64).reshape(-1)
            if xyz.size < 3:
                continue
            rows.append({
                "frame_number": frame_number,
                "performer_id": performer_id,
                "point_name": point_name,
                "x": float(xyz[0]),
                "y": float(xyz[1]),
                "z": float(xyz[2]),
            })
    return rows
