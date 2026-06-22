"""Unit tests for the segment-length / human-shape diagnostics.

Deterministic and fast — builds synthetic skeletons from the canonical ratios,
no pipeline or test data needed.
"""
import numpy as np

from freemocap.core.kinematics.segment_lengths import (
    StreamingSegmentLengthMonitor,
    build_segment_length_report,
    canonical_bone_length_ratios,
)

_HEIGHT_MM = 1700.0


def _synthetic_body_positions(
    *, n_frames: int = 120, height_mm: float = _HEIGHT_MM, scale: dict[str, float] | None = None
) -> dict[str, np.ndarray]:
    """Build a perfectly anthropometric limb skeleton (each segment = ratio*height).

    ``scale`` multiplies specific bone-key ratios to deliberately deform a segment.
    Returns ``{landmark: (n_frames, 3)}`` (static pose repeated across frames).
    """
    ratios = canonical_bone_length_ratios()
    scale = scale or {}
    positions: dict[str, np.ndarray] = {}

    def chain(joints: list[tuple[str, str | None]], y_offset: float) -> None:
        x = 0.0
        for name, bone_key in joints:
            if bone_key is not None:
                x += ratios[bone_key] * height_mm * scale.get(bone_key, 1.0)
            positions[name] = np.array([x, y_offset, 0.0])

    chain([("left_shoulder", None),
           ("left_elbow", "left_shoulder->left_elbow"),
           ("left_wrist", "left_elbow->left_wrist")], 0.0)
    chain([("right_shoulder", None),
           ("right_elbow", "right_shoulder->right_elbow"),
           ("right_wrist", "right_elbow->right_wrist")], 100.0)
    chain([("left_hip", None),
           ("left_knee", "left_hip->left_knee"),
           ("left_ankle", "left_knee->left_ankle")], 500.0)
    chain([("right_hip", None),
           ("right_knee", "right_hip->right_knee"),
           ("right_ankle", "right_knee->right_ankle")], 600.0)

    return {name: np.tile(p, (n_frames, 1)) for name, p in positions.items()}


def test_synthetic_human_is_human_shaped():
    report = build_segment_length_report(_synthetic_body_positions())
    assert report.human_shape_violations() == [], report.summary()
    assert abs(report.implied_height_median_mm - _HEIGHT_MM) < 1.0
    assert report.implied_height_cv < 1e-6


def test_deformed_segment_is_flagged():
    # Triple the left forearm — breaks proportionality and L/R symmetry.
    positions = _synthetic_body_positions(scale={"left_elbow->left_wrist": 3.0})
    report = build_segment_length_report(positions)
    violations = report.human_shape_violations()
    assert violations, "Expected a non-human deformed skeleton to be flagged"
    assert any("CV" in v or "symmet" in v.lower() for v in violations), violations


def test_implausible_scale_is_flagged():
    # A 5 cm-tall "person" is geometrically proportioned but not plausibly human.
    report = build_segment_length_report(_synthetic_body_positions(height_mm=50.0))
    violations = report.human_shape_violations()
    assert any("plausible" in v or "height" in v for v in violations), violations


def test_streaming_monitor_matches_batch():
    positions = _synthetic_body_positions(n_frames=120)
    monitor = StreamingSegmentLengthMonitor(window=120)
    for frame in range(120):
        monitor.update({name: arr[frame] for name, arr in positions.items()})

    assert monitor.n_seen == 120
    report = monitor.report()
    assert report.human_shape_violations() == [], report.summary()
    assert abs(report.implied_height_median_mm - _HEIGHT_MM) < 1.0


def test_streaming_monitor_handles_empty_frames():
    # No triangulation this frame → empty dict → NaN buffers, no crash, not assessable.
    monitor = StreamingSegmentLengthMonitor(window=30)
    for _ in range(30):
        monitor.update({})
    report = monitor.report()
    assert len(report.assessable()) == 0
