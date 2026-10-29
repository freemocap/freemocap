"""Bounded tall serialization for declared numeric channel arrays."""

from collections.abc import Iterator
from dataclasses import dataclass, field, replace

import numpy as np
from numpy.typing import NDArray
import pyarrow as pa

from freemocap.core.recording.sample_encoding.arrow_schema import SAMPLE_SCHEMA
from freemocap.core.recording.data_descriptors.recording_descriptor import Channel
from freemocap.core.data_tensors.layout_definitions import SourceIdentity
from freemocap.core.data_tensors.sample_timeline import SampleTimeline


@dataclass(frozen=True, slots=True)
class SeriesSampling:
    frame_numbers: tuple[int, ...]
    timestamps_s: tuple[float, ...]
    run_id: int
    batch_size: int = 65536
    sample_timeline: SampleTimeline = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.run_id < 0 or self.batch_size < 1:
            raise ValueError("Positive batch size and nonnegative run ID required")
        object.__setattr__(self, "sample_timeline", SampleTimeline(
            timeline_id=f"run:{self.run_id}:samples", clock_id="recording_relative",
            source_identity=SourceIdentity(source_id=f"run:{self.run_id}"),
            sample_ids=self.frame_numbers, timestamps_s=self.timestamps_s,
        ))

    @classmethod
    def from_timeline(cls, *, sample_timeline: SampleTimeline, run_id: int, batch_size: int = 65536) -> "SeriesSampling":
        """Reuse already validated timing across every channel in a publication."""
        if run_id < 0 or batch_size < 1:
            raise ValueError("Positive batch size and nonnegative run ID required")
        result = object.__new__(cls)
        object.__setattr__(result, "frame_numbers", sample_timeline.sample_axis.identifiers)
        object.__setattr__(result, "timestamps_s", tuple(sample_timeline.timestamps_s))
        object.__setattr__(result, "run_id", run_id)
        object.__setattr__(result, "batch_size", batch_size)
        object.__setattr__(result, "sample_timeline", sample_timeline)
        return result


@dataclass(frozen=True, slots=True)
class ChannelSeries:
    channel: Channel
    values: NDArray[np.float64]

    def __post_init__(self) -> None:
        if self.values.ndim != 3 or self.values.shape[1:] != (
            len(self.channel.names),
            len(self.channel.components),
        ):
            raise ValueError(
                "Channel series must have shape (frames, names, components)"
            )
        if np.isinf(self.values).any():
            raise ValueError("Channel series cannot contain infinite values")

    def batches(self, sampling: SeriesSampling) -> Iterator[pa.RecordBatch]:
        if (
            len(sampling.frame_numbers) != self.values.shape[0]
            or len(sampling.timestamps_s) != self.values.shape[0]
        ):
            raise ValueError("Channel series and timing must cover the same frame grid")
        if sampling.batch_size < 1 or sampling.run_id < 0:
            raise ValueError("Positive batch size and nonnegative run ID required")
        channel_layout = self.channel.tensor_layout()
        series_layout = replace(
            channel_layout,
            axes=(sampling.sample_timeline.sample_axis, *channel_layout.axes),
        )
        series_layout.validate_array(self.values)
        # Construct bounded columns directly. A Python dictionary per scalar is
        # expensive and competes with reconstruction threads for the interpreter.
        components = tuple(self.channel.components)
        component_count = len(components)
        values_per_frame = len(self.channel.names) * component_count
        frame_numbers = sampling.sample_timeline.sample_ids
        timestamps = sampling.sample_timeline.timestamps_s
        names = pa.array(self.channel.names, type=pa.string())
        component_names = pa.array(components, type=pa.string())
        units = pa.array(tuple(self.channel.components.values()), type=pa.string())
        # Whole frames permit columnar validation, without exceeding the row bound.
        batch_rows = (sampling.batch_size // values_per_frame) * values_per_frame or sampling.batch_size
        for start in range(0, self.values.size, batch_rows):
            indices = np.arange(start, min(start + batch_rows, self.values.size))
            frames = indices // values_per_frame
            points = (indices // component_count) % len(self.channel.names)
            axes = indices % component_count
            values = self.values[frames, points, axes]
            count = len(indices)
            columns = [
                pa.array(timestamps[frames], type=pa.float64()),
                pa.repeat(pa.scalar(self.channel.sensor_group, type=pa.string()), count),
                pa.array(frame_numbers[frames], type=pa.int64()),
                pa.repeat(pa.scalar(self.channel.source, type=pa.string()), count),
                pa.repeat(pa.scalar(self.channel.reference_frame, type=pa.string()), count),
                pa.repeat(pa.scalar(self.channel.kind, type=pa.string()), count),
                names.take(points), component_names.take(axes),
                pa.array(values, mask=np.isnan(values), type=pa.float64()),
                units.take(axes),
                pa.repeat(pa.scalar(sampling.run_id, type=pa.int64()), count),
            ]
            yield pa.RecordBatch.from_arrays(columns, schema=SAMPLE_SCHEMA)
