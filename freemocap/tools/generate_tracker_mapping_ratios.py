"""Regenerate anatomical_offset ratios so a tracker mapping reproduces the rest pose.

The ``anatomical_offset`` entries in SkellyTracker's body mapping YAMLs claim to be
"recomputed from SkellyForge's rest positions". When the model moves on, the ratios
go stale silently - the mapped junctions land centimetres off the geometry every
other layer authors against. This script closes that loop: drive SkellyTracker's own
``TrackerMapping.apply`` with synthetic T-pose observations taken from
``RestPose``, numerically invert the linear offset form per entry, and print the
corrected ratios (plus a per-landmark error report for the whole mapping).

The offset form is linear in its ratios with the frame basis built independently of
them, so one Newton step through the real runtime recovers exact fractions - this
tool never re-implements the anatomical_offset semantics, it interrogates them.

Usage::

    python -m freemocap.tools.generate_tracker_mapping_ratios <mapping.yaml> [...]

This Core-owned tool composes SkellyForge definitions and SkellyTracker mappings.
It prints proposals and errors; it never writes mapping files.
The companion tests are ``freemocap/tests/test_tracker_mapping_authoring.py``.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np
import yaml

from skellyforge.core.skeleton.pose.rest_pose import RestPose
from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition
from skellytracker.core.io.tracker_mapping import TrackerMapping

# Tracker keypoint name -> standard-human landmark whose REST position stands in
# for it at the synthetic T-pose. Keep in sync with the companion guard test.
_TRACKER_STANDINS: dict[str, str] = {
    "nose": "nose",
    "left_eye": "left_eye",
    "right_eye": "right_eye",
    "left_ear": "left_ear",
    "right_ear": "right_ear",
    "left_shoulder": "left_acromion",
    "right_shoulder": "right_acromion",
    "left_elbow": "left_elbow",
    "right_elbow": "right_elbow",
    "left_wrist": "left_wrist",
    "right_wrist": "right_wrist",
    "left_hip": "left_hip_socket",
    "right_hip": "right_hip_socket",
    "left_knee": "left_knee",
    "right_knee": "right_knee",
    "left_ankle": "left_ankle",
    "right_ankle": "right_ankle",
    "left_big_toe": "left_toe_tip",
    "right_big_toe": "right_toe_tip",
    "left_foot_index": "left_toe_tip",
    "right_foot_index": "right_toe_tip",
    "left_heel": "left_calcaneus",
    "right_heel": "right_calcaneus",
}

_EPSILON = 1e-4


def _synthetic_tpose_tracker_positions(rest_pose: RestPose) -> dict[str, np.ndarray]:
    positions: dict[str, np.ndarray] = {}
    missing: list[str] = []
    for tracker_name, landmark_name in _TRACKER_STANDINS.items():
        try:
            positions[tracker_name] = rest_pose.landmark_positions[landmark_name].array
        except KeyError:
            missing.append(f"{tracker_name} -> {landmark_name}")
    if missing:
        raise ValueError(f"stand-in landmarks absent from the rest pose: {missing}")
    return positions


def _corrected_entries(
    raw_entries: dict,
    rest_positions_by_landmark: dict[str, np.ndarray],
    tracker_positions: dict[str, np.ndarray],
) -> tuple[dict, list[str]]:
    """Return a copy of ``raw_entries`` with every anatomical_offset ratio solved."""
    corrected = copy.deepcopy(raw_entries)
    notes: list[str] = []

    for landmark_name, entry in raw_entries.items():
        if not isinstance(entry, dict) or entry.get("form") != "anatomical_offset":
            continue
        if landmark_name not in rest_positions_by_landmark:
            notes.append(
                f"{landmark_name}: not a skeleton landmark, left untouched"
            )
            continue
        target = rest_positions_by_landmark[landmark_name]

        base_mapping = TrackerMapping(entries=copy.deepcopy(raw_entries))
        base_output = base_mapping.apply(tracker_positions=tracker_positions)
        base_point = base_output.get(landmark_name)
        if base_point is None:
            notes.append(f"{landmark_name}: apply() produced nothing, left untouched")
            continue

        axis_names = list(entry["offset"].keys())
        columns: list[np.ndarray] = []
        for axis_name in axis_names:
            perturbed = copy.deepcopy(raw_entries)
            perturbed[landmark_name]["offset"][axis_name] += _EPSILON
            perturbed_output = TrackerMapping(entries=perturbed).apply(
                tracker_positions=tracker_positions
            )
            columns.append((perturbed_output[landmark_name] - base_point) / _EPSILON)

        delta = np.array(target) - base_point
        matrix = np.column_stack(columns)
        solution, *_ = np.linalg.lstsq(matrix, delta, rcond=None)

        old_ratios = {k: float(entry["offset"][k]) for k in axis_names}
        new_ratios = {
            k: float(old_ratios[k] + v) for k, v in zip(axis_names, solution)
        }
        corrected[landmark_name]["offset"] = {
            k: round(v, 6) for k, v in new_ratios.items()
        }

        residual = float(
            np.linalg.norm(
                np.asarray(TrackerMapping(entries=copy.deepcopy(corrected)).apply(
                    tracker_positions=tracker_positions
                )[landmark_name])
                - target
            )
        )
        old_error = float(np.linalg.norm(np.asarray(base_point) - target))
        moved = any(
            abs(new_ratios[k] - old_ratios[k]) > 5e-6 for k in axis_names
        )
        if moved:
            notes.append(
                f"{landmark_name}: {old_ratios} -> "
                f"{ {k: round(v, 6) for k, v in new_ratios.items()} }  "
                f"(error {old_error:.1f}mm -> {residual:.3f}mm)"
            )
    return corrected, notes


def _error_report(
    mapping_path: Path,
    rest_positions_by_landmark: dict[str, np.ndarray],
    tracker_positions: dict[str, np.ndarray],
) -> list[tuple[str, float]]:
    mapping = TrackerMapping.from_yaml(mapping_path)
    output = mapping.apply(tracker_positions=tracker_positions)
    rows = []
    for landmark_name, position in sorted(output.items()):
        authored = rest_positions_by_landmark.get(landmark_name)
        if authored is None:
            continue
        rows.append(
            (landmark_name, float(np.linalg.norm(np.asarray(position) - authored)))
        )
    return rows


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    skeleton = SkeletonDefinition.from_default_yaml()
    rest_pose = RestPose.from_default_yaml(skeleton=skeleton)
    rest_positions_by_landmark = {
        name: rest_pose.landmark_positions[name].array for name in skeleton.landmarks
    }
    tracker_positions = _synthetic_tpose_tracker_positions(rest_pose)

    exit_code = 0
    for mapping_path in argv:
        path = Path(mapping_path)
        raw_entries = yaml.safe_load(path.read_text(encoding="utf-8"))
        corrected, notes = _corrected_entries(
            raw_entries=raw_entries,
            rest_positions_by_landmark=rest_positions_by_landmark,
            tracker_positions=tracker_positions,
        )
        print(f"\n=== {path.name}: corrected ratios ===")
        if notes:
            for note in notes:
                print(f"  {note}")
        else:
            print("  every anatomical_offset already reproduces the rest pose")

        stale_threshold_mm = 2.0
        offenders = [
            (name, error)
            for name, error in _error_report(path, rest_positions_by_landmark, tracker_positions)
            if error > stale_threshold_mm
        ]
        if offenders:
            exit_code = 1
            print(f"  current-file landmarks off the rest pose by >{stale_threshold_mm}mm:")
            for name, error in offenders:
                print(f"    {name}: {error:.1f}mm")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
