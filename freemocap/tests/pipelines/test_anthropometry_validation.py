"""E2E: validate that the trusted posthoc output is actually *human-shaped*."""
import logging

import pytest

from freemocap.core.kinematics.segment_lengths import LIMB_SEGMENTS

logger = logging.getLogger(__name__)


@pytest.mark.e2e
def test_posthoc_output_is_human_shaped(posthoc_segment_report):
    report = posthoc_segment_report
    logger.info("=== HUMAN-SHAPE CHECK ===")
    logger.info("\n" + report.summary())

    assessable = report.assessable()
    logger.info(
        f"Assessable segments: {len(assessable)}/{len(report.stats)}  "
        f"(need >= {report.thresholds.min_assessable_segments})"
    )
    for name, s in sorted(assessable.items()):
        logger.info(
            f"  {name}: median={s.median_mm:.1f}mm  temporal_cv={s.temporal_cv:.3f}  "
            f"implied_H={s.implied_height_mm:.0f}mm  valid={s.valid_fraction:.0%}"
        )

    assert len(assessable) >= report.thresholds.min_assessable_segments, (
        f"Too few assessable segments:\n{report.summary()}"
    )

    violations = report.human_shape_violations(check_rigidity=True)
    if violations:
        logger.warning(f"Human-shape violations ({len(violations)}):")
        for v in violations:
            logger.warning(f"  FAIL: {v}")
    else:
        logger.info("No human-shape violations — PASS")

    assert not violations, (
        "Posthoc output is not human-shaped:\n  - "
        + "\n  - ".join(violations)
        + "\n"
        + report.summary()
    )


@pytest.mark.e2e
def test_posthoc_implied_height_is_plausible(posthoc_segment_report):
    report = posthoc_segment_report
    height_mm = report.implied_height_median_mm
    lo, hi = report.thresholds.min_height_mm, report.thresholds.max_height_mm
    logger.info(
        f"Implied standing height: {height_mm:.0f}mm  "
        f"(plausible range: {lo:.0f}–{hi:.0f}mm)"
    )
    assert lo <= height_mm <= hi, (
        f"Implied standing height {height_mm:.0f}mm is not physically plausible\n"
        + report.summary()
    )
    logger.info(f"Implied height {height_mm:.0f}mm is within plausible range — PASS")


@pytest.mark.e2e
def test_posthoc_measures_all_limb_segments(posthoc_segment_report):
    measured = set(posthoc_segment_report.stats)
    expected = {seg.name for seg in LIMB_SEGMENTS}
    missing = expected - measured
    logger.info(
        f"Limb segments: expected={sorted(expected)}  "
        f"measured={sorted(measured)}  missing={sorted(missing)}"
    )
    assert not missing, f"Posthoc output missing limb segments: {sorted(missing)}"
    logger.info(f"All {len(expected)} limb segments measured — PASS")
