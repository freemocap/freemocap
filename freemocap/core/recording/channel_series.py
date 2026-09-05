"""Bounded tall serialization for declared numeric channel arrays."""

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
import pyarrow as pa

from freemocap.core.recording.recording_data import SAMPLE_SCHEMA
from freemocap.core.recording.recording_metadata import Channel


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
        rows: list[dict[str, object]] = []
        for index, (frame, timestamp) in enumerate(
            zip(sampling.frame_numbers, sampling.timestamps_s, strict=True)
        ):
            for point, name in enumerate(self.channel.names):
                for axis, (component, units) in enumerate(
                    self.channel.components.items()
                ):
                    value = float(self.values[index, point, axis])
                    rows.append(
                        dict(
                            timestamp_s=timestamp,
                            sensor_group=self.channel.sensor_group,
                            frame_number=frame,
                            source=self.channel.source,
                            reference_frame=self.channel.reference_frame,
                            channel=self.channel.kind,
                            name=name,
                            component=component,
                            value=None if np.isnan(value) else value,
                            units=units,
                            run_id=sampling.run_id,
                        )
                    )
                    if len(rows) == sampling.batch_size:
                        yield pa.RecordBatch.from_pylist(rows, schema=SAMPLE_SCHEMA)
                        rows.clear()
        if rows:
            yield pa.RecordBatch.from_pylist(rows, schema=SAMPLE_SCHEMA)
