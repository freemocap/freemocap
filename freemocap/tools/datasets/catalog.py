"""Acquire raw reference recordings; processing readiness is a separate concern."""

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import requests
from filelock import FileLock


@dataclass(frozen=True)
class RecordingDataset:
    name: str
    url: str
    expected_frame_count: int | None


TEST_DATA = RecordingDataset(
    name="freemocap_test_data",
    url="https://github.com/freemocap/skellysamples/releases/download/test_data_v06_09_25/freemocap_test_data.zip",
    expected_frame_count=222,
)
SAMPLE_DATA = RecordingDataset(
    name="freemocap_sample_data",
    url="https://github.com/freemocap/skellysamples/releases/download/sample_data_v06_12_25/freemocap_sample_data.zip",
    expected_frame_count=1108,
)


def synchronized_video_directory(recording: Path) -> Path:
    """Locate raw videos without claiming they are decoded or processed."""
    candidates = [
        folder
        for folder in (
            recording / "synchronized_videos",
            recording / "videos" / "synchronized",
        )
        if folder.is_dir()
        and any(
            path.is_file() and path.suffix.lower() == ".mp4"
            for path in folder.iterdir()
        )
    ]
    if len(candidates) != 1:
        raise ValueError(
            f"Expected one synchronized video directory in {recording}; "
            f"found {len(candidates)}. Existing files were not replaced."
        )
    return candidates[0]


def acquire_recording(
    dataset: RecordingDataset, *, recordings_root: Path | None = None
) -> Path:
    """Reuse an existing recording or publish a completely extracted download.

    Both datasets contain the same calibration-and-movement recording at
    different temporal sampling densities. Neither requires a bundled
    calibration or processed Parquet file.
    """
    root = (
        recordings_root
        if recordings_root is not None
        else Path.home() / "freemocap_data" / "recordings"
    )
    root = root.expanduser().resolve()
    if dataset.name not in (TEST_DATA.name, SAMPLE_DATA.name):
        raise ValueError(f"Unknown recording dataset: {dataset.name}")
    destination = root / dataset.name
    root.mkdir(parents=True, exist_ok=True)
    with FileLock(str(root / f".{dataset.name}.download.lock"), timeout=600):
        if destination.exists():
            synchronized_video_directory(destination)
            return destination

        with TemporaryDirectory(prefix=f".{dataset.name}-", dir=root) as temporary:
            staging = Path(temporary)
            archive_path = staging / "download.zip"
            with requests.get(
                dataset.url, stream=True, timeout=(10, 300)
            ) as response:
                response.raise_for_status()
                with archive_path.open("wb") as output:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        output.write(chunk)

            extracted = staging / "extracted"
            extracted.mkdir()
            with ZipFile(archive_path) as archive:
                for member in archive.infolist():
                    name = member.filename.replace("\\", "/")
                    target = (extracted / name).resolve()
                    if ":" in name or not target.is_relative_to(extracted.resolve()):
                        raise ValueError(f"Archive member escapes extraction: {name}")
                archive.extractall(extracted)

            candidates = set()
            for folder in extracted.rglob("*"):
                if not folder.is_dir():
                    continue
                if folder.name == "synchronized_videos":
                    candidates.add(folder.parent)
                elif folder.name == "synchronized" and folder.parent.name == "videos":
                    candidates.add(folder.parent.parent)
            if len(candidates) != 1:
                raise ValueError(
                    f"Expected one recording in {dataset.url}; "
                    f"found {len(candidates)}"
                )
            recording = candidates.pop()
            synchronized_video_directory(recording)
            recording.rename(destination)
    return destination
