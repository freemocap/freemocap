"""E2E: posthoc calibration pipeline on the 7x5 charuco test recording.

The ``calibration_toml_path`` fixture (session-scoped, in conftest) runs the
calibration once with the correct 7x5 board; these tests verify its outputs.
"""
import cv2
import pytest


@pytest.mark.e2e
def test_calibration_writes_last_successful_toml(calibration_toml_path):
    assert calibration_toml_path.exists()
    assert calibration_toml_path.stat().st_size > 0


@pytest.mark.e2e
def test_calibration_writes_recording_local_toml(test_recording_path, calibration_toml_path):
    expected = test_recording_path / f"{test_recording_path.stem}_camera_calibration.toml"
    assert expected.exists(), f"Expected recording-local calibration TOML at {expected}"
    assert expected.stat().st_size > 0


@pytest.mark.e2e
def test_calibration_annotated_videos_match_source(test_recording_path, calibration_toml_path):
    annotated_dir = test_recording_path / "annotated_videos"
    assert annotated_dir.exists(), f"annotated_videos/ not found in {test_recording_path}"

    source = sorted((test_recording_path / "synchronized_videos").glob("*.mp4"))
    annotated = sorted(annotated_dir.glob("*.mp4"))
    assert annotated, "No annotated videos produced"
    assert len(annotated) == len(source), (
        f"Annotated count ({len(annotated)}) != source count ({len(source)})"
    )

    for ann_path, src_path in zip(annotated, source):
        ann = cv2.VideoCapture(str(ann_path))
        src = cv2.VideoCapture(str(src_path))
        try:
            assert int(ann.get(cv2.CAP_PROP_FRAME_WIDTH)) == int(src.get(cv2.CAP_PROP_FRAME_WIDTH))
            assert int(ann.get(cv2.CAP_PROP_FRAME_HEIGHT)) == int(src.get(cv2.CAP_PROP_FRAME_HEIGHT))
            assert int(ann.get(cv2.CAP_PROP_FRAME_COUNT)) == int(src.get(cv2.CAP_PROP_FRAME_COUNT))
        finally:
            ann.release()
            src.release()
