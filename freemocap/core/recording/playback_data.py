"""Canonical recording views for timestamp-based playback without reconstruction work."""

from contextlib import contextmanager
from collections.abc import Iterator
from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from pydantic import Field, model_validator

from freemocap.core.recording.recording_data import DESCRIPTOR_KEY, SAMPLE_SCHEMA
from freemocap.core.recording.recording_metadata import (
    Channel,
    Descriptor,
    RecordingMetadata,
    StaticChannel,
    SourceKind,
)
from freemocap.core.recording.observation_recording_models import CameraRecordingDefinition
from freemocap.core.recording.recording_reader import read_static_channels
from freemocap.core.recording.sample_conventions import SampleComponent
from freemocap.core.recording.shared_recording_file import shared_recording_file
from freemocap.core.streaming.message_composer import compose_messages
from freemocap.core.streaming.message_model import ModelDefinition
from freemocap.core.streaming.producers.producer_contexts import StreamContext
from freemocap.core.types.channel_kind import ChannelKind


class PlaybackWindowRequest(Descriptor):
    run_id: int = Field(ge=0)
    revision: str = Field(min_length=1)
    sensor_groups: tuple[str, ...] = Field(min_length=1)
    start_s: float = Field(allow_inf_nan=False)
    end_s: float = Field(allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_interval(self) -> "PlaybackWindowRequest":
        if not 0 < self.end_s - self.start_s <= 3:
            raise ValueError(
                "Playback queries require an interval of at most three seconds"
            )
        return self


class PlaybackTimeline(Descriptor):
    sensor_group: str
    source: str
    frame_numbers: tuple[int, ...]
    timestamps_s: tuple[float, ...]

    @model_validator(mode="after")
    def validate_grid(self) -> "PlaybackTimeline":
        if not self.frame_numbers or len(self.frame_numbers) != len(self.timestamps_s):
            raise ValueError("Playback timeline requires matching nonempty frame and time arrays")
        if any(frame < 0 for frame in self.frame_numbers) or any(
            not math.isfinite(timestamp) for timestamp in self.timestamps_s
        ):
            raise ValueError("Playback timeline requires nonnegative frames and finite timestamps")
        if any(right <= left for left, right in zip(self.frame_numbers, self.frame_numbers[1:])) or any(
            right <= left for left, right in zip(self.timestamps_s, self.timestamps_s[1:])
        ):
            raise ValueError("Playback timeline must advance strictly in frame number and time")
        return self


class PlaybackMedia(Descriptor):
    video_filename: str
    nominal_fps: float = Field(gt=0, allow_inf_nan=False)
    timeline: PlaybackTimeline

    @classmethod
    def from_camera(cls, *, camera: CameraRecordingDefinition, timeline: PlaybackTimeline) -> "PlaybackMedia":
        return cls(video_filename=camera.video_filename, nominal_fps=camera.nominal_fps, timeline=timeline)


class PlaybackRun(Descriptor):
    run_id: int
    models: tuple[ModelDefinition, ...]
    channels: tuple[Channel, ...]
    static_channels: tuple[StaticChannel, ...]
    timelines: tuple[PlaybackTimeline, ...]
    media: tuple[PlaybackMedia, ...]


class PlaybackManifest(Descriptor):
    recording_id: str
    revision: str
    selected_run_id: int
    runs: tuple[PlaybackRun, ...]


class PlaybackChannelData(Descriptor):
    channel: Channel
    frame_numbers: tuple[int, ...]
    timestamps_s: tuple[float, ...]
    values: tuple[float | None, ...]


class PlaybackWindow(Descriptor):
    revision: str
    run_id: int
    start_s: float
    end_s: float
    channels: tuple[PlaybackChannelData, ...]


class StalePlaybackRevision(ValueError):
    """The selected recording has been replaced since its manifest was loaded."""


@dataclass(frozen=True)
class RecordingView:
    parquet: pq.ParquetFile
    metadata: RecordingMetadata
    revision: str


@contextmanager
def recording_view(path: Path) -> Iterator[RecordingView]:
    # One open file binds descriptor, revision and rows to the same published result.
    with shared_recording_file(path) as source:
        stat = os.fstat(source.fileno())
        revision = hashlib.sha256(
            f"{stat.st_dev}:{stat.st_ino}:{stat.st_size}:{stat.st_mtime_ns}".encode()
        ).hexdigest()
        with pq.ParquetFile(source) as parquet:
            if not parquet.schema_arrow.equals(SAMPLE_SCHEMA, check_metadata=False):
                raise ValueError("Invalid canonical recording schema")
            payload = (parquet.schema_arrow.metadata or {}).get(DESCRIPTOR_KEY)
            if payload is None:
                raise ValueError("Missing recording descriptor")
            metadata = RecordingMetadata.model_validate_json(payload)
            if metadata.recording_id != path.parent.name:
                raise ValueError("Recording identity does not match its folder")
            yield RecordingView(parquet=parquet, metadata=metadata, revision=revision)


def playback_manifest(path: Path) -> PlaybackManifest:
    with recording_view(path) as view:
        grids: dict[tuple[int, str, str], dict[int, float]] = {}
        for batch in view.parquet.iter_batches(batch_size=65536):
            selected = batch.filter(
                pc.and_(
                    pc.equal(batch.column("channel"), ChannelKind.TIMESTAMPS),
                    pc.equal(batch.column("component"), SampleComponent.TIMESTAMP),
                )
            )
            columns = selected.to_pydict()
            for run, group, source, frame, timestamp in zip(
                columns["run_id"],
                columns["sensor_group"],
                columns["source"],
                columns["frame_number"],
                columns["timestamp_s"],
                strict=True,
            ):
                grid = grids.setdefault((run, group, source), {})
                if frame in grid and grid[frame] != timestamp:
                    raise ValueError("Inconsistent playback timestamps")
                grid[frame] = timestamp
        runs: list[PlaybackRun] = []
        for run_id, run in view.metadata.runs.items():
            composition = compose_messages(
                StreamContext(
                    skeletons=tuple(model.to_bundle() for model in run.models.values())
                )
            )
            timelines = tuple(
                PlaybackTimeline(
                    sensor_group=group,
                    source=source,
                    frame_numbers=tuple(sorted(grid)),
                    timestamps_s=tuple(grid[frame] for frame in sorted(grid)),
                )
                for (saved_run, group, source), grid in grids.items()
                if saved_run == run_id
            )
            media: list[PlaybackMedia] = []
            for timeline in timelines:
                source = run.sources[timeline.source]
                if source.kind == SourceKind.CAMERA:
                    media.append(PlaybackMedia.from_camera(
                        camera=CameraRecordingDefinition.model_validate(source.definition),
                        timeline=timeline,
                    ))
            runs.append(
                PlaybackRun(
                    run_id=run_id,
                    models=composition.models,
                    channels=run.channels,
                    static_channels=read_static_channels(run),
                    timelines=timelines,
                    media=tuple(media),
                )
            )
        return PlaybackManifest(
            recording_id=view.metadata.recording_id,
            revision=view.revision,
            selected_run_id=view.metadata.selected_run_id,
            runs=tuple(runs),
        )


def playback_window(*, path: Path, request: PlaybackWindowRequest) -> PlaybackWindow:
    with recording_view(path) as view:
        if view.revision != request.revision:
            raise StalePlaybackRevision(
                "Recording changed; reload the playback manifest"
            )
        run = view.metadata.runs[request.run_id]
        if not set(request.sensor_groups).issubset(run.sensor_groups):
            raise ValueError("Unknown playback sensor group")
        batches: list[pa.RecordBatch] = []
        row_count = 0
        timestamp_index = SAMPLE_SCHEMA.get_field_index("timestamp_s")
        for index in range(view.parquet.num_row_groups):
            stats = (
                view.parquet.metadata.row_group(index)
                .column(timestamp_index)
                .statistics
            )
            if (
                stats is not None
                and stats.has_min_max
                and (stats.max < request.start_s or stats.min >= request.end_s)
            ):
                continue
            for batch in view.parquet.iter_batches(
                row_groups=[index], batch_size=65536
            ):
                mask = pc.and_(
                    pc.equal(batch.column("run_id"), request.run_id),
                    pc.is_in(
                        batch.column("sensor_group"),
                        value_set=pa.array(request.sensor_groups),
                    ),
                )
                mask = pc.and_(
                    mask, pc.greater_equal(batch.column("timestamp_s"), request.start_s)
                )
                mask = pc.and_(
                    mask, pc.less(batch.column("timestamp_s"), request.end_s)
                )
                selected = batch.filter(mask).replace_schema_metadata(None)
                row_count += selected.num_rows
                if row_count > 2_000_000:
                    raise ValueError(
                        "Playback window is too large; request a shorter interval"
                    )
                if selected.num_rows:
                    batches.append(selected)
        table = pa.Table.from_batches(batches, schema=SAMPLE_SCHEMA)
        channels: list[PlaybackChannelData] = []
        for channel in run.channels:
            if channel.sensor_group not in request.sensor_groups:
                continue
            mask = pc.and_(
                pc.equal(table["sensor_group"], channel.sensor_group),
                pc.equal(table["source"], channel.source),
            )
            mask = pc.and_(mask, pc.equal(table["channel"], channel.kind))
            mask = pc.and_(
                mask,
                pc.is_null(table["reference_frame"])
                if channel.reference_frame is None
                else pc.equal(table["reference_frame"], channel.reference_frame),
            )
            selected = table.filter(mask).to_pydict()
            frames = tuple(sorted(set(selected["frame_number"])))
            if not frames:
                continue
            frame_indices = {frame: index for index, frame in enumerate(frames)}
            names = {name: index for index, name in enumerate(channel.names)}
            components = {name: index for index, name in enumerate(channel.components)}
            values: list[float | None] = [None] * (
                len(frames) * len(names) * len(components)
            )
            seen: set[int] = set()
            timestamps: dict[int, float] = {}
            for frame, timestamp, name, component, value in zip(
                selected["frame_number"],
                selected["timestamp_s"],
                selected["name"],
                selected["component"],
                selected["value"],
                strict=True,
            ):
                offset = (frame_indices[frame] * len(names) + names[name]) * len(
                    components
                ) + components[component]
                if offset in seen or (
                    frame in timestamps and timestamps[frame] != timestamp
                ):
                    raise ValueError("Duplicate or inconsistent playback sample")
                seen.add(offset)
                timestamps[frame] = timestamp
                values[offset] = value
            if len(seen) != len(values):
                raise ValueError("Incomplete playback sample grid")
            channels.append(
                PlaybackChannelData(
                    channel=channel,
                    frame_numbers=frames,
                    timestamps_s=tuple(timestamps[frame] for frame in frames),
                    values=tuple(values),
                )
            )
        return PlaybackWindow(
            revision=view.revision,
            run_id=request.run_id,
            start_s=request.start_s,
            end_s=request.end_s,
            channels=tuple(channels),
        )
