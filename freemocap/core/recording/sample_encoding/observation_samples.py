"""Translate SkellyTracker observations and explicit recording-clock times to Arrow."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import islice
from functools import lru_cache
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
from freemocap.core.tracking.observation_series import ObservationFrame, RecordingObservationSeries

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.recording.data_descriptors.recording_descriptor import Channel


@dataclass(frozen=True, slots=True)
class TimedObservation:
    observation: Observation | ObservationFrame
    capture_timestamp_s: float


def _require_timing_channel(channel: Channel) -> None:
    if (
        channel.kind != ChannelKind.TIMESTAMPS
        or channel.stage != ProcessingStage.TIMING
        or channel.reference_frame is not None
        or channel.components != {SampleComponent.TIMESTAMP: SampleUnit.SECONDS}
        or channel.names not in ((TimingSampleName.CAPTURE,), (TimingSampleName.SYNCHRONIZED,))
    ):
        raise ValueError("Expected a capture or synchronized TIMESTAMPS channel")


def timing_series_batches(*, sampling: SeriesSampling, channel: Channel) -> Iterator[pa.RecordBatch]:
    """Publish the existing validated clock directly as numerical Arrow columns."""
    _require_timing_channel(channel)
    yield from ChannelSeries(channel=channel, values=sampling.sample_timing.timestamps_s[:, None, None]).batches(sampling)


def timing_batches(*, samples: Iterable[tuple[int, float]], channel: Channel,
                   run_id: int, batch_size: int) -> Iterator[pa.RecordBatch]:
    """Bound an iterable clock adapter; no scalar sample dictionaries are created."""
    if batch_size < 1 or run_id < 0:
        raise ValueError("batch_size must be positive and run_id nonnegative")
    _require_timing_channel(channel)
    iterator = iter(samples)
    last_frame, last_timestamp = -1, -math.inf
    while chunk := tuple(islice(iterator, batch_size)):
        frames, timestamps = zip(*chunk, strict=True)
        sampling = SeriesSampling(frame_numbers=frames, timestamps_s=timestamps, run_id=run_id, batch_size=batch_size)
        if frames[0] <= last_frame or timestamps[0] <= last_timestamp:
            raise ValueError("Timing frames and finite timestamps must strictly increase")
        last_frame, last_timestamp = frames[-1], timestamps[-1]
        yield from timing_series_batches(sampling=sampling, channel=channel)


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



BOX_COMPONENTS = ('x1', 'y1', 'x2', 'y2', 'confidence', 'detector_ran')


def _require_box_channel(channel: Channel) -> None:
    if (channel.kind != ChannelKind.BOXES_2D or channel.stage != ProcessingStage.OBSERVATIONS
            or channel.reference_frame is None or set(channel.components) != set(BOX_COMPONENTS)):
        raise ValueError("Expected an image-frame BOXES_2D observation channel")


def _box_sampling(sampling: SeriesSampling, channel: Channel) -> SeriesSampling:
    # A complete frame is the minimum box batch. Preserve ChannelSeries' general
    # strict row-bound contract, while keeping this publisher's grids rectangular.
    width = len(channel.names) * len(channel.components)
    return SeriesSampling.from_timeline(sample_timing=sampling.sample_timing, run_id=sampling.run_id,
                                       batch_size=max(width, sampling.batch_size))


@lru_cache(maxsize=256)
def _box_stage_layout(layout: tuple) -> tuple:
    """Match Tracker's stack traversal, including duplicate stage-name precedence."""
    children = {}
    for path, name, _ in layout:
        children.setdefault(path[:-1], []).append((path, name))
    pending = list(children.get((), ()))
    ordered = []
    while pending:
        path, name = pending.pop()
        ordered.append((path, name))
        pending.extend(children.get(path, ()))
    return tuple(ordered)


def _recording_box_values(series: RecordingObservationSeries, selection: slice, channel: Channel) -> np.ndarray:
    """Select complete frame/stage arrays without reconstructing Tracker boxes."""
    layouts = series.layout_indices[selection]
    if np.any(layouts < 0):
        raise ValueError('Observation frame has not been delivered')
    counts, boxes = series.box_counts[selection], series.box_values[selection]
    detectors = series.detector_values[selection]
    values = np.full((len(layouts), len(channel.names), len(BOX_COMPONENTS)), np.nan)
    present = np.zeros(values.shape[:2], dtype=bool)
    targets = {name: index for index, name in enumerate(channel.names)}
    for layout_id in np.unique(layouts):
        rows = np.flatnonzero(layouts == layout_id)
        layout = series.layouts[layout_id]
        stage_columns = tuple((name, series.stage_paths.index(path)) for path, name in _box_stage_layout(layout))
        for name, column in stage_columns:
            present_rows = rows[counts[rows, column] > 0]
            if not len(present_rows):
                continue
            if name not in targets:
                raise ValueError('Observation contains undeclared bounding-box stage names')
            target = targets[name]
            selected = boxes[present_rows, column, 0]
            values[present_rows, target, :-1] = selected
            present[present_rows, target] = True
            matching_columns = [item_column for item_name, item_column in stage_columns if item_name == name]
            values[present_rows, target, -1] = detectors[np.ix_(present_rows, matching_columns)].any(axis=1)
    _validate_box_values(values, present)
    return values[..., [BOX_COMPONENTS.index(component) for component in channel.components]]


def _validate_box_values(values: np.ndarray, present: np.ndarray) -> None:
    if np.isinf(values[..., :BOX_COMPONENTS.index('confidence')]).any():
        raise ValueError('Infinite bounding-box coordinate')
    if not np.isfinite(values[..., BOX_COMPONENTS.index('confidence')][present]).all():
        raise ValueError('Invalid bounding-box confidence')


def box_series_batches(*, series: RecordingObservationSeries, sampling: SeriesSampling,
                       channel: Channel) -> Iterator[pa.RecordBatch]:
    """Publish recording-owned box tensors in bounded, complete frame batches."""
    _require_box_channel(channel)
    if not np.array_equal(sampling.sample_timing.sample_ids, series.frame_numbers) or not series.delivered.all():
        raise ValueError('Box values and sampling must cover the same delivered frame grid')
    sampling = _box_sampling(sampling, channel)
    frame_count = max(1, sampling.batch_size // (len(channel.names) * len(channel.components)))
    for start in range(0, len(series), frame_count):
        stop = min(start + frame_count, len(series))
        values = _recording_box_values(series, slice(start, stop), channel)
        selected = SeriesSampling.from_timeline(sample_timing=sampling.sample_timing.slice_samples(start, stop),
            run_id=sampling.run_id, batch_size=sampling.batch_size)
        yield from ChannelSeries(channel=channel, values=values).batches(selected)


def box_batches(*, samples: Iterable[TimedObservation], channel: Channel,
                run_id: int, batch_size: int) -> Iterator[pa.RecordBatch]:
    """Adapt individual observations into bounded tensors, then publish columns.

    A stage without a box has nulls for every component, including detector_ran.
    Batches contain whole frames; one frame is the minimum even for a smaller row limit.
    """
    if batch_size < 1 or run_id < 0:
        raise ValueError("batch_size must be positive and run_id nonnegative")
    _require_box_channel(channel)
    width = len(channel.names) * len(channel.components)
    frame_count = max(1, batch_size // width)
    iterator = iter(samples)
    last_frame, last_timestamp = -1, -math.inf
    targets = {name: index for index, name in enumerate(channel.names)}
    component_axes = [BOX_COMPONENTS.index(component) for component in channel.components]
    while chunk := tuple(islice(iterator, frame_count)):
        values = np.full((len(chunk), len(channel.names), len(BOX_COMPONENTS)), np.nan)
        present = np.zeros(values.shape[:2], dtype=bool)
        frames, timestamps = [], []
        for row, sample in enumerate(chunk):
            observation, timestamp = sample.observation, sample.capture_timestamp_s
            if not math.isfinite(timestamp) or timestamp <= last_timestamp:
                raise ValueError('Capture timestamps must be finite and strictly increasing')
            if observation.frame_number <= last_frame:
                raise ValueError('Observation frame numbers must be nonnegative and strictly increasing')
            last_frame, last_timestamp = observation.frame_number, timestamp
            frames.append(observation.frame_number)
            timestamps.append(timestamp)
            if isinstance(observation, ObservationFrame):
                if isinstance(observation.camera_series, RecordingObservationSeries):
                    # Already in channel component order; restore canonical order for
                    # the common publication operation below.
                    selected = _recording_box_values(observation.camera_series,
                        slice(observation.sample_index, observation.sample_index + 1), channel)[0]
                    values[row][:, component_axes] = selected
                    present[row] = np.isfinite(selected[:, tuple(channel.components).index('confidence')])
                continue
            stages = tuple(_walk_stages(observation))
            # Match the established stage-tree override ordering for repeated names.
            for name, stage in stages:
                if not stage.bounding_boxes:
                    continue
                if name not in targets:
                    raise ValueError('Observation contains undeclared bounding-box stage names')
                box = stage.bounding_boxes[0]
                corners = (box.x1, box.y1, box.x2, box.y2)
                present[row, targets[name]] = True
                values[row, targets[name]] = (*corners, box.confidence,
                    any(item.detector_ran for stage_name, item in stages if stage_name == name))
        _validate_box_values(values, present)
        sampling = SeriesSampling(frame_numbers=tuple(frames), timestamps_s=tuple(timestamps),
                                  run_id=run_id, batch_size=max(width, batch_size))
        yield from ChannelSeries(channel=channel, values=values[..., component_axes]).batches(sampling)


def _walk_stages(observation: Observation) -> Iterator[tuple[str, object]]:
    """Every stage in the tree, keyed by its own name."""
    pending = list(observation.stages.values())
    while pending:
        stage = pending.pop()
        pending.extend(stage.children.values())
        yield stage.name, stage
