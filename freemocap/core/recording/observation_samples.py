"""Translate SkellyTracker observations and explicit recording-clock times to Arrow."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
import math
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.core.recording.sample_conventions import (
    SampleComponent,
    SampleUnit,
    TimingSampleName,
)

import pyarrow as pa
from skellytracker.core.data_primitives.observation import Observation

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.recording.recording_data import SAMPLE_SCHEMA
from freemocap.core.recording.recording_metadata import Channel


@dataclass(frozen=True, slots=True)
class TimedObservation:
    observation: Observation
    capture_timestamp_s: float


def timing_batches(
    *,
    samples: Iterable[tuple[int, float]],
    channel: Channel,
    run_id: int,
    batch_size: int,
) -> Iterator[pa.RecordBatch]:
    """Store capture or synchronized timing from an explicitly mapped recording clock."""
    if batch_size < 1 or run_id < 0:
        raise ValueError("batch_size must be positive and run_id nonnegative")
    if (
        channel.kind != ChannelKind.TIMESTAMPS
        or channel.stage != ProcessingStage.TIMING
        or channel.reference_frame is not None
        or channel.components != {SampleComponent.TIMESTAMP: SampleUnit.SECONDS}
        or channel.names
        not in ((TimingSampleName.CAPTURE,), (TimingSampleName.SYNCHRONIZED,))
    ):
        raise ValueError("Expected a capture or synchronized TIMESTAMPS channel")
    rows: list[dict[str, str | int | float | None]] = []
    last_frame = -1
    last_timestamp = -math.inf
    for frame_number, timestamp in samples:
        if (
            frame_number <= last_frame
            or not math.isfinite(timestamp)
            or timestamp <= last_timestamp
        ):
            raise ValueError(
                "Timing frames and finite timestamps must strictly increase"
            )
        last_frame, last_timestamp = frame_number, timestamp
        rows.append(
            dict(
                timestamp_s=timestamp,
                sensor_group=channel.sensor_group,
                frame_number=frame_number,
                source=channel.source,
                reference_frame=None,
                channel=channel.kind,
                name=channel.names[0],
                component=SampleComponent.TIMESTAMP,
                value=timestamp,
                units=SampleUnit.SECONDS,
                run_id=run_id,
            )
        )
        if len(rows) == batch_size:
            yield pa.RecordBatch.from_pylist(rows, schema=SAMPLE_SCHEMA)
            rows.clear()
    if rows:
        yield pa.RecordBatch.from_pylist(rows, schema=SAMPLE_SCHEMA)


def observation_batches(
    *,
    samples: Iterable[TimedObservation],
    channel: Channel,
    run_id: int,
    batch_size: int,
) -> Iterator[pa.RecordBatch]:
    """Store named image coordinates without guessing capture time from frame rate.

    Point names come from SkellyTracker's stage-tree flattening. The channel declares
    the complete point set even when detection returns only a subset or no points.
    Camera orientation and image dimensions belong to its reference-frame descriptor.
    """
    if batch_size < 1 or run_id < 0:
        raise ValueError("batch_size must be positive and run_id nonnegative")
    if (
        channel.kind != ChannelKind.OVERLAY_2D
        or channel.stage != ProcessingStage.OBSERVATIONS
        or channel.reference_frame is None
        or channel.components
        != {
            SampleComponent.X: SampleUnit.PIXELS,
            SampleComponent.Y: SampleUnit.PIXELS,
            SampleComponent.VISIBILITY: SampleUnit.DIMENSIONLESS,
        }
    ):
        raise ValueError("Expected an image-frame OVERLAY_2D observation channel")
    rows: list[dict[str, str | int | float | None]] = []
    last_frame = -1
    last_timestamp = -math.inf
    declared = set(channel.names)
    for sample in samples:
        observation = sample.observation
        timestamp = sample.capture_timestamp_s
        if not math.isfinite(timestamp) or timestamp <= last_timestamp:
            raise ValueError(
                "Capture timestamps must be finite and strictly increasing"
            )
        if observation.frame_number <= last_frame:
            raise ValueError(
                "Observation frame numbers must be nonnegative and strictly increasing"
            )
        last_frame, last_timestamp = observation.frame_number, timestamp
        points = observation.to_keypoints()
        if len(set(points.names)) != len(points.names) or set(points.names) - declared:
            raise ValueError("Observation contains duplicate or undeclared point names")
        indices = {name: index for index, name in enumerate(points.names)}
        for name in channel.names:
            values: dict[str, float | None] = {
                SampleComponent.X: None,
                SampleComponent.Y: None,
                SampleComponent.VISIBILITY: 0.0,
            }
            if name in indices:
                index = indices[name]
                visibility = float(points.visibility[index])
                if not math.isfinite(visibility) or not 0 <= visibility <= 1:
                    raise ValueError(f"Invalid visibility for {name}")
                values[SampleComponent.VISIBILITY] = visibility
                for component, coordinate in zip(
                    (SampleComponent.X, SampleComponent.Y),
                    points.xy[index],
                    strict=True,
                ):
                    value = float(coordinate)
                    if math.isinf(value):
                        raise ValueError(f"Infinite image coordinate for {name}")
                    values[component] = None if math.isnan(value) else value
            for component, units in channel.components.items():
                rows.append(
                    dict(
                        timestamp_s=timestamp,
                        sensor_group=channel.sensor_group,
                        frame_number=observation.frame_number,
                        source=channel.source,
                        reference_frame=channel.reference_frame,
                        channel=channel.kind,
                        name=name,
                        component=component,
                        value=values[component],
                        units=units,
                        run_id=run_id,
                    )
                )
                if len(rows) == batch_size:
                    yield pa.RecordBatch.from_pylist(rows, schema=SAMPLE_SCHEMA)
                    rows.clear()
    if rows:
        yield pa.RecordBatch.from_pylist(rows, schema=SAMPLE_SCHEMA)
