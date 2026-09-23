"""Read-only validation of downloaded recordings, before pipeline preparation.

Run with the repository Python: -B -m freemocap.tests.inspect_recording_datasets.
Container presentation timestamps describe playback, not necessarily capture time.
"""

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

import av

from freemocap.tests.recording_datasets import (
    RecordingDataset, SAMPLE_DATA, TEST_DATA, synchronized_video_directory,
)


@dataclass(frozen=True)
class VideoInspection:
    filename: str
    sha256: str
    width: int
    height: int
    decoded_frames: int
    reported_frames: int
    nominal_fps: float | None
    first_timestamp_s: float
    last_timestamp_s: float
    minimum_interval_s: float
    maximum_interval_s: float
    presentation_timing_sha256: str


def inspect_video(path: Path) -> VideoInspection:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    timestamps: list[float] = []
    dimensions: set[tuple[int, int]] = set()
    with av.open(str(path)) as container:
        if len(container.streams.video) != 1:
            raise ValueError(f"Expected one video stream: {path}")
        stream = container.streams.video[0]
        reported_frames = stream.frames
        fps = float(stream.average_rate) if stream.average_rate else None
        for frame in container.decode(video=0):
            if frame.pts is None or frame.time_base is None:
                raise ValueError(f"Missing presentation timestamp: {path}")
            timestamp = float(frame.pts * frame.time_base)
            if not math.isfinite(timestamp) or (timestamps and timestamp <= timestamps[-1]):
                raise ValueError(f"Non-increasing or invalid presentation timestamp: {path}")
            timestamps.append(timestamp)
            dimensions.add((frame.width, frame.height))
    if len(timestamps) < 2 or len(dimensions) != 1:
        raise ValueError(f"Expected multiple frames with fixed dimensions: {path}")
    if reported_frames and reported_frames != len(timestamps):
        raise ValueError(f"Decoded frame count disagrees with container: {path}")
    if fps is not None and (not math.isfinite(fps) or fps <= 0):
        raise ValueError(f"Invalid nominal FPS: {path}")
    width, height = dimensions.pop()
    intervals = [right - left for left, right in zip(timestamps, timestamps[1:])]
    return VideoInspection(
        filename=path.name, sha256=digest.hexdigest(), width=width, height=height,
        decoded_frames=len(timestamps), reported_frames=reported_frames,
        nominal_fps=fps, first_timestamp_s=timestamps[0], last_timestamp_s=timestamps[-1],
        minimum_interval_s=min(intervals), maximum_interval_s=max(intervals),
        presentation_timing_sha256=hashlib.sha256(
            json.dumps([timestamp.hex() for timestamp in timestamps]).encode("ascii")
        ).hexdigest(),
    )


def inspect_recording(dataset: RecordingDataset, *, recordings_root: Path) -> dict:
    recording = recordings_root.expanduser().resolve() / dataset.name
    folder = synchronized_video_directory(recording)
    paths = sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() == ".mp4")
    if len(paths) != 3:
        raise ValueError(f"Expected three reference-camera videos, found {len(paths)}: {recording}")
    videos = [inspect_video(path) for path in paths]
    counts = {video.decoded_frames for video in videos}
    if len(counts) != 1:
        raise ValueError(f"Camera frame counts disagree: {recording}")
    if len({video.presentation_timing_sha256 for video in videos}) != 1:
        raise ValueError(f"Camera presentation timelines disagree: {recording}")
    count = counts.pop()
    if dataset.expected_frame_count is not None and count != dataset.expected_frame_count:
        raise ValueError(f"Expected {dataset.expected_frame_count} frames, decoded {count}: {recording}")
    board_path = recording / "charuco_board_info.json"
    board = json.loads(board_path.read_text(encoding="utf-8")) if board_path.is_file() else None
    expected_board = {"square_size_mm": 58, "num_squares_height": 5, "num_squares_width": 7}
    if not isinstance(board, dict) or any(board.get(key) != value for key, value in expected_board.items()):
        raise ValueError(f"Expected 7x5 board metadata with 58 mm squares: {board_path}")
    return {
        "dataset": dataset.name,
        "recording": str(recording),
        "videos": [asdict(video) for video in videos],
        "board_metadata": board,
        "calibration_files": sorted(path.name for path in recording.glob("*.toml")),
        "parquet_files": sorted(str(path.relative_to(recording)) for path in recording.rglob("*.parquet")),
        "timestamp_sidecars": sorted(
            str(path.relative_to(recording)) for path in recording.rglob("*")
            if path.is_file() and "timestamp" in str(path.relative_to(recording)).lower()
        ),
        "timing_note": "Presentation timestamps establish video playback cadence, not original capture cadence or camera synchronization.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recordings-root", type=Path, default=Path.home() / "freemocap_data" / "recordings")
    parser.add_argument("--dataset", choices=("test", "sample", "all"), default="all")
    arguments = parser.parse_args()
    datasets = {"test": (TEST_DATA,), "sample": (SAMPLE_DATA,), "all": (TEST_DATA, SAMPLE_DATA)}
    for dataset in datasets[arguments.dataset]:
        print(json.dumps(inspect_recording(dataset, recordings_root=arguments.recordings_root), indent=2), flush=True)


if __name__ == "__main__":
    main()
