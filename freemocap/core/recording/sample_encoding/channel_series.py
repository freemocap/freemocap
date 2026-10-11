"""Bounded tall serialization for declared numeric channel arrays."""

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
import pyarrow as pa

from freemocap.core.recording.sample_encoding.arrow_schema import SAMPLE_SCHEMA
from freemocap.core.recording.data_descriptors.recording_descriptor import Channel


@dataclass(frozen=True, slots=True)
class SeriesSampling:
    frame_numbers: tuple[int, ...]
    timestamps_s: tuple[float, ...]
    run_id: int
    batch_size: int = 65536


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
        # Construct bounded columns directly. A Python dictionary per scalar is
        # expensive and competes with reconstruction threads for the interpreter.
        components = tuple(self.channel.components)
        component_count = len(components)
        values_per_frame = len(self.channel.names) * component_count
        frame_numbers = np.asarray(sampling.frame_numbers, dtype=np.int64)
        timestamps = np.asarray(sampling.timestamps_s, dtype=np.float64)
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
