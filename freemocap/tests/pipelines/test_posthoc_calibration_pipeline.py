"""E2E: posthoc calibration pipeline on the 7x5 charuco test recording."""
import logging

import cv2
import pytest
from pathlib import Path

from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.tests.pipelines.real_data_numeric_bounds import (
    MAX_REJECTED_OBSERVATION_FRACTION,
    MAX_REPROJECTION_ERROR_PX,
    MIN_OBSERVATIONS_USED,
)

logger = logging.getLogger(__name__)


@pytest.mark.e2e
def test_calibration_writes_last_successful_toml(calibration_toml_path):
    logger.info(f"Checking last-successful TOML: {calibration_toml_path}")
    assert calibration_toml_path.exists()
    size_kb = calibration_toml_path.stat().st_size / 1024
    assert size_kb > 0
    logger.info(f"TOML exists and is non-empty ({size_kb:.1f} KB) — PASS")


@pytest.mark.e2e
def test_calibration_writes_recording_local_toml(test_recording_path, calibration_toml_path):
    expected = test_recording_path / f"{test_recording_path.stem}_camera_calibration.toml"
    logger.info(f"Checking recording-local TOML: {expected}")
    assert expected.exists(), f"Expected recording-local calibration TOML at {expected}"
    size_kb = expected.stat().st_size / 1024
    assert size_kb > 0
    logger.info(f"Recording-local TOML exists ({size_kb:.1f} KB) — PASS")


@pytest.mark.e2e
def test_calibration_annotated_videos_match_source(test_recording_path, calibration_toml_path):
    annotated_dir = test_recording_path / "annotated_videos"
    logger.info(f"Checking annotated videos in: {annotated_dir}")
    assert annotated_dir.exists(), f"annotated_videos/ not found in {test_recording_path}"

    source = sorted((test_recording_path / "synchronized_videos").glob("*.mp4"))
    annotated = sorted(annotated_dir.glob("*.mp4"))
    logger.info(f"Source videos: {len(source)}  |  Annotated videos: {len(annotated)}")
    assert annotated, "No annotated videos produced"
    assert len(annotated) == len(source), (
        f"Annotated count ({len(annotated)}) != source count ({len(source)})"
    )

    for ann_path, src_path in zip(annotated, source):
        logger.info(f"  Comparing: {ann_path.name}  vs  {src_path.name}")
        ann = cv2.VideoCapture(str(ann_path))
        src = cv2.VideoCapture(str(src_path))
        try:
            ann_w = int(ann.get(cv2.CAP_PROP_FRAME_WIDTH))
            ann_h = int(ann.get(cv2.CAP_PROP_FRAME_HEIGHT))
            ann_n = int(ann.get(cv2.CAP_PROP_FRAME_COUNT))
            src_w = int(src.get(cv2.CAP_PROP_FRAME_WIDTH))
            src_h = int(src.get(cv2.CAP_PROP_FRAME_HEIGHT))
            src_n = int(src.get(cv2.CAP_PROP_FRAME_COUNT))
            logger.info(
                f"    annotated: {ann_w}x{ann_h} {ann_n}f  |  "
                f"source: {src_w}x{src_h} {src_n}f"
            )
            assert ann_w == src_w
            assert ann_h == src_h
            assert ann_n == src_n
        finally:
            ann.release()
            src.release()
    logger.info("All annotated videos match source dimensions and frame counts — PASS")


@pytest.mark.e2e
def test_calibration_solve_is_numerically_sane(calibration_toml_path):
    """The solved calibration is well-conditioned, not just present.

    Checks the solve quality on the real data without any semantic reading of it:
    sub-pixel mean reprojection, enough observations, and a small rejected fraction.
    """
    result = CalibrationResult.load_anipose_toml(Path(calibration_toml_path))
    logger.info(
        f"Calibration solve: reproj={result.reprojection_error_px:.3f}px  "
        f"observations={result.n_observations_used}  "
        f"rejected={result.n_observations_rejected}"
    )

    assert result.reprojection_error_px < MAX_REPROJECTION_ERROR_PX, (
        f"mean reprojection error {result.reprojection_error_px:.3f}px >= "
        f"{MAX_REPROJECTION_ERROR_PX}px — solve is not sub-pixel clean"
    )
    assert result.n_observations_used >= MIN_OBSERVATIONS_USED, (
        f"only {result.n_observations_used} observations used "
        f"(expected >= {MIN_OBSERVATIONS_USED})"
    )
    rejected_fraction = result.n_observations_rejected / max(result.n_observations_used, 1)
    assert rejected_fraction <= MAX_REJECTED_OBSERVATION_FRACTION, (
        f"rejected {result.n_observations_rejected}/{result.n_observations_used} "
        f"observations ({rejected_fraction:.1%}) — too much data was thrown away"
    )
    logger.info("Calibration solve quality within bounds — PASS")
