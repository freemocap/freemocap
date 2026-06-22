"""E2E: validate that the trusted posthoc output is actually *human-shaped*.

Goes beyond "not all NaN": measures limb-segment lengths from the posthoc 3D
output and checks they are in anthropometric proportion (consistent implied
standing height across segments), temporally rigid, and left/right symmetric —
using the canonical body model's bone-length ratios as the reference.

The realtime-vs-posthoc equivalence check lives in test_realtime_pipeline.py
(it needs a live realtime run); this module pins down the posthoc reference.
"""
import pytest

from freemocap.core.kinematics.segment_lengths import LIMB_SEGMENTS


@pytest.mark.e2e
def test_posthoc_output_is_human_shaped(posthoc_segment_report):
    report = posthoc_segment_report
    print("\n" + report.summary())

    # Enough limb segments were actually measured from the output.
    assert len(report.assessable()) >= report.thresholds.min_assessable_segments, (
        f"Too few assessable segments:\n{report.summary()}"
    )

    violations = report.human_shape_violations(check_rigidity=True)
    assert not violations, (
        "Posthoc output is not human-shaped:\n  - "
        + "\n  - ".join(violations)
        + "\n"
        + report.summary()
    )


@pytest.mark.e2e
def test_posthoc_implied_height_is_plausible(posthoc_segment_report):
    height_mm = posthoc_segment_report.implied_height_median_mm
    assert 1000.0 <= height_mm <= 2200.0, (
        f"Implied standing height {height_mm:.0f}mm is not physically plausible\n"
        + posthoc_segment_report.summary()
    )


@pytest.mark.e2e
def test_posthoc_measures_all_limb_segments(posthoc_segment_report):
    # Every limb segment should be measurable from a full-body recording.
    measured = set(posthoc_segment_report.stats)
    expected = {seg.name for seg in LIMB_SEGMENTS}
    missing = expected - measured
    assert not missing, f"Posthoc output missing limb segments: {sorted(missing)}"
