import pytest
from pydantic import ValidationError

from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig


@pytest.mark.parametrize("config_type", [CameraNodeConfig, PosthocMocapPipelineConfig])
@pytest.mark.parametrize("hand_count", [0, 1, 3, 4])
def test_two_sided_presets_reject_ineffective_hand_counts(config_type, hand_count):
    with pytest.raises(ValidationError, match="mediapipe_num_hands"):
        config_type(mediapipe_num_hands=hand_count)


@pytest.mark.parametrize("config_type", [CameraNodeConfig, PosthocMocapPipelineConfig])
def test_two_sided_count_matches_tracker_recipe(config_type):
    settings = config_type(detector_type="mediapipe", mediapipe_num_hands=2)
    config = (settings.skeleton_tracker_config if isinstance(settings, CameraNodeConfig)
              else settings.tracker_config)
    hands = [child for child in config.stages[0].children if child.name.endswith("_hand")]
    assert {child.name for child in hands} == {"left_hand", "right_hand"}
    assert [child.keypoint_detectors[0].num_hands for child in hands] == [1, 1]


@pytest.mark.parametrize("config_type,field_name", [
    (CameraNodeConfig, "skeleton_tracker_config"), (PosthocMocapPipelineConfig, "tracker_config")])
def test_configuration_is_resolved_once_and_conflicting_inputs_rejected(config_type, field_name):
    from unittest.mock import patch
    from skellytracker.core.config.tracker_config import TrackerConfig
    from freemocap.core.tracking.tracker_factory import tracker_config_for_settings
    with patch("freemocap.core.tracking.tracker_factory.tracker_config_for_settings",
               wraps=tracker_config_for_settings) as resolve:
        original = config_type(detector_type="mediapipe")
        assert resolve.call_count == 1
    serialized = original.model_dump(round_trip=True)
    restored = config_type.model_validate(serialized)
    assert getattr(restored, field_name) == getattr(original, field_name)
    with pytest.raises(ValidationError, match="must match the selected tracking preset"):
        config_type(**{field_name: TrackerConfig(stages=[])})
    serialized["mediapipe_detection_confidence"] = 0.9
    with pytest.raises(ValidationError, match="must match the selected tracking preset"):
        config_type.model_validate(serialized)
