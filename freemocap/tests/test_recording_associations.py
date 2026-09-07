import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from freemocap.core.pipeline.posthoc.video_group_helper import _load_manifest_videos


def test_missing_associations_are_unresolved(tmp_path: Path) -> None:
    assert _load_manifest_videos(recording_path=tmp_path) is None


def test_invalid_declared_associations_do_not_fall_back(tmp_path: Path) -> None:
    metadata = tmp_path / f"{tmp_path.name}_info.json"
    metadata.write_text(json.dumps({"videos": {"source": 42}}), encoding="utf-8")
    with pytest.raises(ValidationError):
        _load_manifest_videos(recording_path=tmp_path)


def test_conflicting_declarations_fail(tmp_path: Path) -> None:
    for suffix, filename in (("info", "first.mp4"), ("recording_info", "second.mp4")):
        metadata = tmp_path / f"{tmp_path.name}_{suffix}.json"
        metadata.write_text(json.dumps({"videos": {"source": filename}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Conflicting video associations"):
        _load_manifest_videos(recording_path=tmp_path)


def test_invalid_json_does_not_fall_back(tmp_path: Path) -> None:
    metadata = tmp_path / f"{tmp_path.name}_info.json"
    metadata.write_text("{", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        _load_manifest_videos(recording_path=tmp_path)
