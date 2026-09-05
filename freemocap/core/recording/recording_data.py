"""Typed scalar batches with bounded validation state per channel trajectory."""

from dataclasses import dataclass, field
import hashlib
import math
import struct

import pyarrow as pa

from freemocap.core.recording.recording_metadata import Channel, RecordingMetadata


SAMPLE_SCHEMA = pa.schema(
    [
        pa.field("timestamp_s", pa.float64(), nullable=False),
        pa.field("sensor_group", pa.string(), nullable=False),
        pa.field("frame_number", pa.int64(), nullable=False),
        pa.field("source", pa.string(), nullable=False),
        pa.field("reference_frame", pa.string()),
        pa.field("channel", pa.string(), nullable=False),
        pa.field("name", pa.string(), nullable=False),
        pa.field("component", pa.string(), nullable=False),
        pa.field("value", pa.float64()),
        pa.field("units", pa.string(), nullable=False),
        pa.field("run_id", pa.int64(), nullable=False),
    ]
)
DESCRIPTOR_KEY = b"freemocap.recording"
TrajectoryKey = tuple[int, str, str, str | None, str, str, str]
ContextKey = tuple[int, str, str, str | None]


@dataclass
class SampleValidator:
    metadata: RecordingMetadata
    last_samples: dict[TrajectoryKey, tuple[int, float]] = field(default_factory=dict)
    timing_digests: dict[TrajectoryKey, bytes] = field(default_factory=dict)
    counts: dict[TrajectoryKey, int] = field(default_factory=dict)
    channel_index: dict[tuple[int, str, str, str | None, str], Channel] = field(
        init=False
    )
    pending_rotations: dict[
        tuple[int, str, str, str | None, str, str], tuple[int, dict[str, float | None]]
    ] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.channel_index = {
            (
                run_id,
                channel.sensor_group,
                channel.source,
                channel.reference_frame,
                channel.kind,
            ): channel
            for run_id, run in self.metadata.runs.items()
            for channel in run.channels
        }

    def accept(self, *, batch: pa.RecordBatch) -> None:
        if not batch.schema.equals(SAMPLE_SCHEMA, check_metadata=False):
            raise ValueError("Sample batch does not match the recording schema")
        for schema_field, column in zip(SAMPLE_SCHEMA, batch.columns, strict=True):
            if not schema_field.nullable and column.null_count:
                raise ValueError(f"Null values in required column {schema_field.name}")
        # Conversion is bounded by the caller's batch, never the complete recording.
        columns = batch.to_pydict()
        for index in range(batch.num_rows):
            run_id = columns["run_id"][index]
            group = columns["sensor_group"][index]
            source = columns["source"][index]
            reference = columns["reference_frame"][index]
            kind = columns["channel"][index]
            name = columns["name"][index]
            component = columns["component"][index]
            channel = self.channel_index.get((run_id, group, source, reference, kind))
            if channel is None:
                raise ValueError(
                    f"Undeclared channel: {(run_id, group, source, reference, kind)}"
                )
            if (
                name not in channel.names
                or channel.components.get(component) != columns["units"][index]
            ):
                raise ValueError(
                    f"Unknown name/component or incorrect units: {name}/{component}"
                )
            frame = columns["frame_number"][index]
            timestamp = columns["timestamp_s"][index]
            value = columns["value"][index]
            if (
                frame < 0
                or not math.isfinite(timestamp)
                or (value is not None and not math.isfinite(value))
            ):
                raise ValueError(
                    "Samples require nonnegative frame numbers and finite numbers or null values"
                )
            if kind in ("ROTATIONS_LOCAL", "ROTATIONS_WORLD"):
                rotation_key = (run_id, group, source, reference, kind, name)
                pending_frame, components = self.pending_rotations.setdefault(
                    rotation_key, (frame, {})
                )
                if pending_frame != frame:
                    raise ValueError(
                        "Quaternion components must be contiguous by sample"
                    )
                components[component] = value
                if len(components) == 4:
                    finite_values = [
                        item for item in components.values() if item is not None
                    ]
                    if finite_values and (
                        len(finite_values) != 4
                        or abs(sum(item * item for item in finite_values) - 1.0) > 1e-5
                    ):
                        raise ValueError(
                            "Quaternion must be unit length or entirely null"
                        )
                    del self.pending_rotations[rotation_key]
            key = (run_id, group, source, reference, kind, name, component)
            previous = self.last_samples.get(key)
            if previous is not None and (
                frame <= previous[0] or timestamp <= previous[1]
            ):
                raise ValueError(
                    f"Duplicate or non-increasing trajectory sample: {key}, frame {frame}"
                )
            self.timing_digests[key] = hashlib.sha256(
                self.timing_digests.get(key, b"") + struct.pack("<qd", frame, timestamp)
            ).digest()
            self.last_samples[key] = (frame, timestamp)
            self.counts[key] = self.counts.get(key, 0) + 1

    def finish(self) -> None:
        if self.pending_rotations:
            raise ValueError("Incomplete quaternion sample")
        context_digests: dict[ContextKey, bytes] = {}
        for (
            run_id,
            group,
            source,
            reference,
            kind,
        ), channel in self.channel_index.items():
            expected = self.metadata.runs[run_id].sensor_groups[group].sample_count
            for name in channel.names:
                for component in channel.components:
                    key = (run_id, group, source, reference, kind, name, component)
                    if self.counts.get(key, 0) != expected:
                        raise ValueError(
                            f"Incomplete channel coverage for {key}: expected {expected} samples"
                        )
                    if expected:
                        context = (run_id, group, source, reference)
                        digest = self.timing_digests[key]
                        if context_digests.setdefault(context, digest) != digest:
                            raise ValueError(
                                f"Inconsistent component timestamps/frame numbers in {context}"
                            )
