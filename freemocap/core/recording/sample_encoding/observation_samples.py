"""Translate SkellyTracker observations and explicit recording-clock times to Arrow."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
import math
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.core.recording.data_descriptors.sample_conventions import (
    SampleComponent,
    SampleUnit,
    TimingSampleName,
)

import numpy as np
from freemocap.core.tracking.observation_arrays import observation_arrays, point_selection
import pyarrow as pa
from freemocap.core.recording.sample_encoding.channel_series import ChannelSeries, SeriesSampling
from skellytracker.core.data_primitives.observation import Observation

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.recording.sample_encoding.arrow_schema import SAMPLE_SCHEMA
from freemocap.core.recording.data_descriptors.recording_descriptor import Channel


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
    last_frame = -1
    last_timestamp = -math.inf
    component_axes = [("x", "y", "visibility").index(name) for name in channel.components]
    frames_per_batch = max(1, batch_size // (len(channel.names) * len(channel.components)))
    values = np.empty((frames_per_batch, len(channel.names), len(channel.components)), dtype=np.float64)
    frames: list[int] = []
    timestamps: list[float] = []
    for sample in samples:
        observation = sample.observation
        timestamp = sample.capture_timestamp_s
        if not math.isfinite(timestamp) or timestamp <= last_timestamp:
            raise ValueError("Capture timestamps must be finite and strictly increasing")
        if observation.frame_number <= last_frame:
            raise ValueError("Observation frame numbers must be nonnegative and strictly increasing")
        last_frame, last_timestamp = observation.frame_number, timestamp
        points = observation_arrays(observation)
        source_indices, indices = point_selection(points.point_names, channel.names)
        if not np.isfinite(points.confidence_scores).all() or np.any((points.confidence_scores < 0) | (points.confidence_scores > 1)):
            raise ValueError("Invalid observation visibility")
        coordinates = points.image_coordinates
        if np.isinf(coordinates).any():
            raise ValueError("Infinite image coordinate")
        frame_values = values[len(frames)]
        frame_values[:, :2] = np.nan
        frame_values[:, 2] = 0.0
        frame_values[indices, :2] = coordinates[source_indices]
        frame_values[indices, 2] = points.confidence_scores[source_indices]
        frames.append(observation.frame_number)
        timestamps.append(timestamp)
        if len(frames) == frames_per_batch:
            yield from ChannelSeries(channel=channel, values=values[:, :, component_axes]).batches(SeriesSampling(
                frame_numbers=tuple(frames), timestamps_s=tuple(timestamps), run_id=run_id, batch_size=batch_size))
            frames.clear()
            timestamps.clear()
    if frames:
        yield from ChannelSeries(channel=channel, values=values[:len(frames), :, component_axes]).batches(SeriesSampling(
            frame_numbers=tuple(frames), timestamps_s=tuple(timestamps), run_id=run_id, batch_size=batch_size))



def box_batches(
    *,
    samples: Iterable[TimedObservation],
    channel: Channel,
    run_id: int,
    batch_size: int,
) -> Iterator[pa.RecordBatch]:
    """Store each detection stage's bounding box beside the points measured inside it.

    Walks the stage tree directly rather than going through `Observation.to_keypoints()`:
    that flattening keeps only keypoints, which is exactly where boxes were being lost.

    The channel declares the complete stage set, so a stage that detected nothing on a
    frame still emits its row with a null value — the same complete-coverage contract
    every other channel holds to.
    """
    if batch_size < 1 or run_id < 0:
        raise ValueError("batch_size must be positive and run_id nonnegative")
    if (
        channel.kind != ChannelKind.BOXES_2D
        or channel.stage != ProcessingStage.OBSERVATIONS
        or channel.reference_frame is None
        or set(channel.components) != {
            SampleComponent.X1, SampleComponent.Y1,
            SampleComponent.X2, SampleComponent.Y2,
            SampleComponent.CONFIDENCE, SampleComponent.DETECTOR_RAN,
        }
    ):
        raise ValueError("Expected an image-frame BOXES_2D observation channel")
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
        boxes = _stage_boxes(observation)
        if set(boxes) - declared:
            raise ValueError("Observation contains undeclared bounding-box stage names")
        for name in channel.names:
            values: dict[str, float | None] = {
                component: None for component in channel.components
            }
            box = boxes.get(name)
            if box is not None:
                corners = (box.x1, box.y1, box.x2, box.y2)
                if any(math.isinf(float(corner)) for corner in corners):
                    raise ValueError(f"Infinite bounding-box coordinate for {name}")
                for component, corner in zip(
                    (SampleComponent.X1, SampleComponent.Y1,
                     SampleComponent.X2, SampleComponent.Y2),
                    corners,
                    strict=True,
                ):
                    coordinate = float(corner)
                    values[component] = None if math.isnan(coordinate) else coordinate
                confidence = float(box.confidence)
                if not math.isfinite(confidence):
                    raise ValueError(f"Invalid bounding-box confidence for {name}")
                values[SampleComponent.CONFIDENCE] = confidence
                values[SampleComponent.DETECTOR_RAN] = (
                    1.0 if _stage_detector_ran(observation, name) else 0.0
                )
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


def _walk_stages(observation: Observation) -> Iterator[tuple[str, object]]:
    """Every stage in the tree, keyed by its own name."""
    pending = list(observation.stages.values())
    while pending:
        stage = pending.pop()
        pending.extend(stage.children.values())
        yield stage.name, stage


def _stage_boxes(observation: Observation) -> dict[str, object]:
    """One box per stage. freemocap runs no multi-person tracker, so a second entry
    would mean the stage contract changed rather than that two subjects are in view."""
    return {
        name: stage.bounding_boxes[0]
        for name, stage in _walk_stages(observation)
        if stage.bounding_boxes
    }


def _stage_detector_ran(observation: Observation, name: str) -> bool:
    return any(
        stage.detector_ran for stage_name, stage in _walk_stages(observation)
        if stage_name == name
    )
