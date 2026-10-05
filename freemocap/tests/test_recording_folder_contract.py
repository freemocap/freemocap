"""Cross-language path contract and non-mutating recording inventory checks."""

import json
from pathlib import Path

import pytest
import yaml

from freemocap.system.recording_structure.recording_structure import RecordingStructure


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = json.loads((ROOT / "shared/recording-contract/paths.json").read_text(encoding="utf-8"))
PRESETS = yaml.safe_load((ROOT / "freemocap-ui/src/store/slices/active-recording/layout-presets/layout-presets.yaml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["walking_01", "walk with spaces", "marche_é"])
def test_canonical_python_and_frontend_paths_match_contract(tmp_path, name):
    structure = RecordingStructure(base_directory=tmp_path, recording_name=name)
    assert set(PRESETS["canonical"]) == set(CONTRACT["canonical"])
    for field, case in CONTRACT["canonical"].items():
        expected = structure.full_path / case["relative"].format(recordingName=name)
        frontend = Path(PRESETS["canonical"][field].format(
            fullPath=structure.full_path.as_posix(), recordingName=name))
        assert getattr(structure, case["python"]) == frontend == expected, field
    assert not structure.full_path.exists(), "Path lookup must not create a recording"


def test_legacy_frontend_paths_match_documented_compatibility_contract(tmp_path):
    assert set(PRESETS["legacy_v1"]) == set(CONTRACT["legacy_v1"])
    for field, relative in CONTRACT["legacy_v1"].items():
        rendered = PRESETS["legacy_v1"][field].format(fullPath=tmp_path.as_posix(), recordingName="walk")
        assert Path(rendered) == tmp_path / relative.format(recordingName="walk"), field


def test_recording_creation_leaves_exports_lazy(tmp_path):
    structure = RecordingStructure(base_directory=tmp_path, recording_name="walk")
    structure.create_on_disk()
    assert structure.videos_synchronized_dir.is_dir()
    assert not structure.exports_dir.exists()
    assert structure.model_dump(mode="json")["exports_dir"] == str(structure.exports_dir)


def test_hybrid_inventory_preserves_capture_and_optional_absence(tmp_path):
    structure = RecordingStructure(base_directory=tmp_path, recording_name="walk")
    legacy_video = structure.full_path / "synchronized_videos"
    legacy_video.mkdir(parents=True)
    capture = structure.full_path / "walk_info.json"
    payload = b'{"recording_name":"walk","camera_configs":{},"unknown_capture_field":42}'
    capture.write_bytes(payload)
    # Inventory checks presence only; scientific validation belongs to the reader.
    structure.data_parquet_path.touch()
    before = sorted(path.relative_to(structure.full_path) for path in structure.full_path.rglob("*"))
    inventory = structure.validate_layout()
    assert inventory.is_legacy_layout
    assert Path(inventory.videos_synchronized.path) == legacy_video
    assert inventory.data_parquet.exists
    assert not inventory.videos_annotated.exists
    assert not inventory.calibration_toml.exists
    assert capture.read_bytes() == payload
    assert before == sorted(path.relative_to(structure.full_path) for path in structure.full_path.rglob("*"))


def test_empty_recording_inventory_does_not_create_directories(tmp_path):
    structure = RecordingStructure(base_directory=tmp_path, recording_name="absent")
    inventory = structure.validate_layout()
    assert not inventory.data_parquet.exists
    assert not structure.full_path.exists()
