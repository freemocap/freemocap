"""Resolved detector configuration and resource ownership at construction."""

from unittest.mock import MagicMock, patch

import pytest
from skellytracker.core import DetectionStageConfig, Tracker, TrackerConfig
from skellytracker.core.detectors.keypoint_detectors.charuco import (
    CharucoDetectorConfig,
)

from freemocap.core.tracking.tracker_factory import build_configured_tracker


@pytest.mark.parametrize("fail", [False, True])
def test_configured_tracker_preserves_nested_config_and_cleans_up(fail: bool) -> None:
    config = TrackerConfig(
        stages=[
            DetectionStageConfig(
                name="parent",
                children=[
                    DetectionStageConfig(
                        name="board", keypoint_detectors=[CharucoDetectorConfig()]
                    )
                ],
            )
        ]
    )
    session = MagicMock()
    with (
        patch(
            "freemocap.core.tracking.tracker_factory.CpuSession.create",
            return_value=session,
        ),
        patch(
            "freemocap.core.tracking.tracker_factory.Tracker.create",
            return_value=Tracker(stages=[]),
        ) as create,
    ):
        if fail:
            create.side_effect = RuntimeError("detector construction failed")
            with pytest.raises(RuntimeError, match="detector construction failed"):
                build_configured_tracker(config=config, batch_size=1)
            session.close.assert_called_once_with()
        else:
            tracker = build_configured_tracker(config=config, batch_size=1)
            assert tracker is create.return_value
            session.close.assert_not_called()
        create.assert_called_once_with(config=config, sessions={"cpu": session})


def test_configured_tracker_rejects_invalid_batch_before_allocation() -> None:
    with pytest.raises(ValueError, match="batch_size must be positive"):
        build_configured_tracker(config=TrackerConfig(stages=[]), batch_size=0)
