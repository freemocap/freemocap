"""Canonical recording views for timestamp-based playback without reconstruction work."""

from freemocap.core.playback.media_selection import PlaybackVideoSource
from freemocap.core.tasks.calibration.shared.calibration_update import CalibrationUpdateRequest
from contextlib import contextmanager
from collections.abc import Iterator
from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq
from pydantic import Field, field_serializer, model_validator

from freemocap.core.recording.sample_encoding.reconstruction_samples import ReconstructionSourceDefinition
from freemocap.core.recording.data_descriptors.recording_descriptor import (
    Channel,
    Descriptor,
    RecordingMetadata,
    StaticChannel,
    SourceKind,
)
from freemocap.core.recording.result_processing.observation_inputs import CameraRecordingDefinition
from freemocap.core.recording.parquet_storage.parquet_reader import read_static_channels, metadata_from_schema
from freemocap.core.recording.data_descriptors.sample_conventions import SampleComponent
from freemocap.core.recording.parquet_storage.shared_file import shared_recording_file
from freemocap.core.streaming.message_composer import compose_messages
from freemocap.core.streaming.message_model import ModelDefinition
from freemocap.core.streaming.producers.producer_contexts import StreamContext
from freemocap.core.types.channel_kind import ChannelKind


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
    video_source: PlaybackVideoSource
    video_filename: str
    nominal_fps: float = Field(gt=0, allow_inf_nan=False)
    timeline: PlaybackTimeline

    @classmethod
    def from_camera(cls, *, camera: CameraRecordingDefinition, timeline: PlaybackTimeline) -> "PlaybackMedia":
        return cls(video_source=PlaybackVideoSource.SYNCHRONIZED, video_filename=camera.video_filename, nominal_fps=camera.nominal_fps, timeline=timeline)


class PlaybackRun(Descriptor):
    model_sources: dict[str, str]
    calibration_updates: dict[str, CalibrationUpdateRequest] = Field(default_factory=dict)
    run_id: int
    models: tuple[ModelDefinition, ...]
    channels: tuple[Channel, ...]
    static_channels: tuple[StaticChannel, ...]
    timelines: tuple[PlaybackTimeline, ...]
    media: tuple[PlaybackMedia, ...]

    @field_serializer("models")
    def serialize_models(self, models: tuple[ModelDefinition, ...]) -> list[dict[str, object]]:
        """Use the same declared wire geometry as live streaming."""
        return [model.to_cbor_message() for model in models]


class PlaybackManifest(Descriptor):
    recording_id: str
    revision: str
    selected_run_id: int
    runs: tuple[PlaybackRun, ...]


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
            metadata = metadata_from_schema(schema=parquet.schema_arrow, path=path)
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
                    model_sources={
                        name: ReconstructionSourceDefinition.model_validate(source.definition).model_id
                        for name, source in run.sources.items()
                        if source.kind == SourceKind.INSTANCE
                        and "model_id" in source.definition
                    },
                    calibration_updates=run.calibration_updates,
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
