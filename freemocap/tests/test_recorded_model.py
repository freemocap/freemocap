"""Scientific definitions restore without a filesystem or a particular skeleton type."""

from pathlib import Path

import numpy as np
from numpy import testing as npt
import pytest
from skellytracker.core.detectors.keypoint_detectors.charuco.charuco_board_definition import (
    CharucoBoardDefinition,
)

from freemocap.core.recording.recorded_model import RecordedModel
from freemocap.core.skeletons.charuco_board_skeleton import build_charuco_board_bundle


def test_board_definition_and_passthrough_mapping_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = build_charuco_board_bundle(
        board=CharucoBoardDefinition.create_letter_size_5x3()
    )
    saved = RecordedModel.from_bundle(bundle)
    loaded = RecordedModel.model_validate_json(saved.model_dump_json())

    def forbid_files(self: Path, *args: object, **kwargs: object) -> str:
        raise AssertionError("Recorded board must not load authored files")

    monkeypatch.setattr(Path, "read_text", forbid_files)
    restored = loaded.to_bundle()
    assert restored.skeleton.joints == {}
    assert RecordedModel.from_bundle(restored) == saved
    points = {
        name: np.array([index, 2.0, 3.0])
        for index, name in enumerate(bundle.tracker_keypoint_names)
    }
    expected = bundle.landmark_mapping.apply(points)
    actual = restored.landmark_mapping.apply(points)
    assert set(actual) == set(expected)
    for name in actual:
        npt.assert_array_equal(actual[name], expected[name])
    for name in bundle.rest_pose.landmark_positions:
        npt.assert_array_equal(
            restored.rest_pose.landmark_positions[name].array,
            bundle.rest_pose.landmark_positions[name].array,
        )
