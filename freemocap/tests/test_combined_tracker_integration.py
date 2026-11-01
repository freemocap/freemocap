"""Application contracts consume Tracker-owned composition and mapping interfaces."""
import pytest

from skellytracker.core.io.tracker_profiles import tracker_profile
from skellytracker.core.tracker import tracker_presets
from freemocap.core.tracking import tracker_factory
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.pipeline.posthoc.annotation_style import build_observation_annotator
from freemocap.core.tasks.mocap.tracker_mappings import tracker_keypoint_names, load_standard_human_mapping
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle


@pytest.mark.parametrize("preset", ["rtmpose", "mediapipe", "rtmw_mediapipe_hands"])
def test_live_and_posthoc_use_tracker_recipes_and_profiles(preset):
    live = CameraNodeConfig(detector_type=preset)
    live_recipe = tracker_factory.tracker_config_for_settings(live)
    assert live.skeleton_tracker_config == live_recipe
    for implementation in ("typed_dataflow",):
        posthoc = PosthocMocapPipelineConfig(detector_type=preset, pipeline_implementation=implementation,
                                           mediapipe_model_complexity=live.mediapipe_model_complexity)
        restored = PosthocMocapPipelineConfig.model_validate_json(posthoc.model_dump_json(by_alias=True, round_trip=True))
        assert restored.tracker_config == posthoc.tracker_config
        assert restored.tracker_config.preset_name == preset
        assert restored.tracker_config.keypoint_assembly == live_recipe.keypoint_assembly
        build_observation_annotator(restored.tracker_config)
    profile = tracker_profile(preset)
    assert tracker_keypoint_names(preset) == tuple(sorted(profile.keypoint_names))
    mapping = load_standard_human_mapping(preset)
    assert mapping.mapping_snapshots() == profile.load_mapping().mapping_snapshots()
    bundle = build_standard_human_bundle(detector_type=preset)
    assert bundle.tracker_keypoint_names == tracker_keypoint_names(preset)


def test_core_recipe_aliases_are_tracker_implementations():
    for name in ("skeleton_tracker_config", "mediapipe_tracker_config",
                 "build_mediapipe_tracker_config"):
        assert getattr(tracker_factory, name) is getattr(tracker_presets, name)


def test_combined_registry_requests_include_hand_backend():
    config = tracker_factory.tracker_config_for_settings(CameraNodeConfig(detector_type="rtmw_mediapipe_hands"))
    requests = tracker_factory.tracker_session_requests(config=config, batch_size=3, execution_provider="cuda")
    assert {request.config.backend for request in requests} == {"onnx", "cpu", "mediapipe"}
    assert next(request.config.execution_provider for request in requests if request.config.backend == "onnx") == "cuda"


def test_board_composition_preserves_combined_output_contract():
    from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition
    config = tracker_presets.combined_tracker_config()
    with_board = tracker_presets.with_charuco_tracker(config, CharucoBoardDefinition.create_letter_size_5x3())
    assert with_board.keypoint_assembly == config.keypoint_assembly
    assert with_board.preset_name == config.preset_name
    assert [stage.name for stage in config.stages] == ["body"]
    assert [stage.name for stage in with_board.stages] == ["body", "charuco"]
    build_observation_annotator(with_board)


@pytest.mark.parametrize("preset,start,message", [
    ("unknown_preset", "observations", "Unknown tracker preset"),
    ("rtmw_mediapipe_hands", "triangulation", "restarting from observations"),
])
def test_reference_cli_rejects_invalid_preset_requests_before_output(tmp_path, preset, start, message):
    from freemocap.tools.datasets.workflow import preflight
    with pytest.raises(ValueError, match=message):
        preflight("test_data", recordings_root=tmp_path / "raw", prepared_root=tmp_path / "output",
                  tracker_preset=preset, start=start)
    assert not (tmp_path / "output").exists()
