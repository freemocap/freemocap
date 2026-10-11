"""Typed scalar batches with bounded validation state per channel trajectory."""

from dataclasses import dataclass, field
import hashlib
import math
import struct

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from freemocap.core.recording.data_descriptors.recording_descriptor import Channel, RecordingMetadata


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
    columnar_rows: int = field(default=0, init=False, compare=False)
    scalar_rows: int = field(default=0, init=False, compare=False)
    last_samples: dict[TrajectoryKey, tuple[int, float]] = field(default_factory=dict)
    timing_digests: dict[TrajectoryKey, bytes] = field(default_factory=dict)
    counts: dict[TrajectoryKey, int] = field(default_factory=dict)
    channel_index: dict[tuple[int, str, str, str | None, str], Channel] = field(
        init=False
    )
    channel_names: dict[tuple[int, str, str, str | None, str], frozenset[str]] = field(init=False)
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
        self.channel_names = {key: frozenset(channel.names) for key, channel in self.channel_index.items()}

    def accept(self, *, batch: pa.RecordBatch) -> None:
        if not batch.schema.equals(SAMPLE_SCHEMA, check_metadata=False):
            raise ValueError("Sample batch does not match the recording schema")
        for schema_field, column in zip(SAMPLE_SCHEMA, batch.columns, strict=True):
            if not schema_field.nullable and column.null_count:
                raise ValueError(f"Null values in required column {schema_field.name}")
        if self._accept_rectangular_batch(batch):
            self.columnar_rows += batch.num_rows
            return
        self._accept_rows(batch)
        self.scalar_rows += batch.num_rows

    def _accept_rows(self, batch: pa.RecordBatch) -> None:
        # Conversion is bounded by the caller's batch, never the complete recording.
        columns = batch.to_pydict()
        # Components on the same sample grid share hash transitions. Reuse the
        # computation, while still tracking and comparing every trajectory.
        # Batch-local storage bounds memory even for malformed/irregular grids.
        digest_transitions: dict[tuple[bytes, bytes], bytes] = {}
        for index in range(batch.num_rows):
            run_id = columns["run_id"][index]
            group = columns["sensor_group"][index]
            source = columns["source"][index]
            reference = columns["reference_frame"][index]
            kind = columns["channel"][index]
            name = columns["name"][index]
            component = columns["component"][index]
            channel_key = (run_id, group, source, reference, kind)
            channel = self.channel_index.get(channel_key)
            if channel is None:
                raise ValueError(
                    f"Undeclared channel: {(run_id, group, source, reference, kind)}"
                )
            if (
                name not in self.channel_names[channel_key]
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
            transition = (self.timing_digests.get(key, b""), struct.pack("<qd", frame, timestamp))
            digest = digest_transitions.get(transition)
            if digest is None:
                digest = hashlib.sha256(transition[0] + transition[1]).digest()
                digest_transitions[transition] = digest
            self.timing_digests[key] = digest
            self.last_samples[key] = (frame, timestamp)
            self.counts[key] = self.counts.get(key, 0) + 1

    def _accept_rectangular_batch(self, batch: pa.RecordBatch) -> bool:
        """Validate the complete frame grids emitted by ChannelSeries in columns.

        Arbitrarily ordered, mixed-channel and partial-frame batches still use the
        scalar validator. Both paths update identical bounded trajectory state.
        """
        if not batch.num_rows or self.pending_rotations:
            return False
        identity = []
        for name in ("run_id", "sensor_group", "source", "reference_frame", "channel"):
            values = pc.unique(batch.column(name))
            if len(values) != 1:
                return False
            identity.append(values[0].as_py())
        channel_key = tuple(identity)
        channel = self.channel_index.get(channel_key)
        if channel is None:
            return False
        components = tuple(channel.components)
        width = len(channel.names) * len(components)
        if batch.num_rows % width:
            return False
        indices = np.arange(batch.num_rows)
        name_indices = pc.index_in(batch.column("name"), value_set=pa.array(channel.names))
        component_indices = pc.index_in(batch.column("component"), value_set=pa.array(components))
        if name_indices.null_count or component_indices.null_count:
            return False
        if not np.array_equal(name_indices.to_numpy(), (indices // len(components)) % len(channel.names)) or not np.array_equal(
                component_indices.to_numpy(), indices % len(components)):
            return False
        expected_units = pa.array(tuple(channel.components.values())).take(indices % len(components))
        if not batch.column("units").equals(expected_units):
            return False
        frames = batch.column("frame_number").to_numpy().reshape(-1, width)
        times = batch.column("timestamp_s").to_numpy().reshape(-1, width)
        if not np.all(frames == frames[:, :1]) or not np.all(times.view(np.uint64) == times[:, :1].view(np.uint64)):
            return False
        frame_grid, time_grid = frames[:, 0], times[:, 0]
        if np.any(frame_grid < 0) or not np.isfinite(time_grid).all() or not pc.all(
                pc.fill_null(pc.is_finite(batch.column("value")), True)).as_py():
            raise ValueError("Samples require nonnegative frame numbers and finite numbers or null values")
        if np.any(frame_grid[1:] <= frame_grid[:-1]) or np.any(time_grid[1:] <= time_grid[:-1]):
            raise ValueError("Duplicate or non-increasing trajectory sample")
        if channel.kind in ("ROTATIONS_LOCAL", "ROTATIONS_WORLD"):
            if len(components) != 4:
                return False
            rotations = batch.column("value").to_numpy(zero_copy_only=False).reshape(-1, 4)
            missing = np.isnan(rotations)
            entirely_null = missing.all(axis=1)
            finite_rotations = rotations[~entirely_null]
            squared_norm = np.zeros(len(finite_rotations))
            # Preserve the scalar checker's addition order at its tolerance boundary.
            for axis in range(4):
                squared_norm += finite_rotations[:, axis] * finite_rotations[:, axis]
            if np.any(missing.any(axis=1) != entirely_null) or np.any(
                    np.abs(squared_norm - 1.) > 1e-5):
                raise ValueError("Quaternion must be unit length or entirely null")
        # Hash the common grid once per distinct prior digest, not once per scalar.
        transitions: dict[bytes, bytes] = {}
        samples = tuple(struct.pack("<qd", int(frame), float(time)) for frame, time in zip(frame_grid, time_grid, strict=True))
        for name in channel.names:
            for component in components:
                key = (*channel_key, name, component)
                previous = self.last_samples.get(key)
                if previous is not None and (frame_grid[0] <= previous[0] or time_grid[0] <= previous[1]):
                    raise ValueError(f"Duplicate or non-increasing trajectory sample: {key}")
                prior = self.timing_digests.get(key, b"")
                digest = transitions.get(prior)
                if digest is None:
                    digest = prior
                    for sample in samples:
                        digest = hashlib.sha256(digest + sample).digest()
                    transitions[prior] = digest
                self.timing_digests[key] = digest
                self.last_samples[key] = (int(frame_grid[-1]), float(time_grid[-1]))
                self.counts[key] = self.counts.get(key, 0) + len(frame_grid)
        return True

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
