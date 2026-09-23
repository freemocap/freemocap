"""Acquisition failures must not damage existing recordings or publish partials."""

import io
from unittest.mock import MagicMock
from zipfile import ZipFile

import pytest
import requests

from freemocap.tests.recording_datasets import (
    SAMPLE_DATA,
    TEST_DATA,
    acquire_recording,
)


def archive_bytes(files):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def mock_download(monkeypatch, payload):
    response = MagicMock()
    response.__enter__.return_value = response
    response.iter_content.return_value = [payload]
    get = MagicMock(return_value=response)
    monkeypatch.setattr(requests, "get", get)
    return get


@pytest.mark.parametrize("dataset", [TEST_DATA, SAMPLE_DATA])
@pytest.mark.parametrize("layout", ["synchronized_videos", "videos/synchronized"])
def test_download_then_reuse_without_processing(monkeypatch, tmp_path, dataset, layout):
    get = mock_download(monkeypatch, archive_bytes({
        f"archive-folder/{layout}/camera.mp4": b"raw-video-placeholder",
    }))
    recording = acquire_recording(dataset, recordings_root=tmp_path)
    assert recording == tmp_path / dataset.name
    assert (recording / layout / "camera.mp4").read_bytes() == b"raw-video-placeholder"
    assert acquire_recording(dataset, recordings_root=tmp_path) == recording
    get.assert_called_once_with(dataset.url, stream=True, timeout=(10, 300))


def test_existing_incomplete_recording_is_preserved(monkeypatch, tmp_path):
    recording = tmp_path / TEST_DATA.name
    recording.mkdir()
    note = recording / "keep.txt"
    note.write_text("user work")
    get = mock_download(monkeypatch, b"unused")
    with pytest.raises(ValueError, match="Existing files were not replaced"):
        acquire_recording(TEST_DATA, recordings_root=tmp_path)
    assert note.read_text() == "user work"
    get.assert_not_called()


def test_failed_download_does_not_publish_recording(monkeypatch, tmp_path):
    get = mock_download(monkeypatch, b"unused")
    get.return_value.raise_for_status.side_effect = requests.HTTPError("503")
    with pytest.raises(requests.HTTPError):
        acquire_recording(TEST_DATA, recordings_root=tmp_path)
    assert not (tmp_path / TEST_DATA.name).exists()
    assert not list(tmp_path.glob(f".{TEST_DATA.name}-*"))


@pytest.mark.parametrize("member", ["../escape.txt", "/escape.txt", "C:/escape.txt"])
def test_archive_escape_is_rejected(monkeypatch, tmp_path, member):
    mock_download(monkeypatch, archive_bytes({
        "recording/synchronized_videos/camera.mp4": b"video",
        member: b"invalid",
    }))
    with pytest.raises(ValueError, match="escapes extraction"):
        acquire_recording(TEST_DATA, recordings_root=tmp_path)
    assert not (tmp_path / TEST_DATA.name).exists()


def test_ambiguous_archive_is_not_published(monkeypatch, tmp_path):
    mock_download(monkeypatch, archive_bytes({
        "first/synchronized_videos/camera.mp4": b"video",
        "second/synchronized_videos/camera.mp4": b"video",
    }))
    with pytest.raises(ValueError, match="Expected one recording"):
        acquire_recording(TEST_DATA, recordings_root=tmp_path)
    assert not (tmp_path / TEST_DATA.name).exists()
