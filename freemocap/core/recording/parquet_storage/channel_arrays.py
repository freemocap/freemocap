"""Named scientific arrays shared by saved-stage readers and export projections."""
from collections.abc import Callable
from concurrent.futures import CancelledError
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path
import tempfile

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from skellyforge.core.data_tensors.layout_definitions import AxisDefinition, SourceIdentity, TensorLayout
from skellyforge.core.data_tensors.data_tensor import CompanionTensor, DataTensor, ScientificProvenance
from skellyforge.core.data_tensors.sample_timing import SampleTiming
from skellyforge.core.data_tensors.time_series import TimeSeries
from freemocap.core.recording.data_descriptors.recording_descriptor import Channel
from freemocap.core.recording.parquet_storage.channel_selection import ChannelSelection
from freemocap.core.recording.parquet_storage.recording_view import RecordingView
from freemocap.core.recording.parquet_storage.selected_batches import ChannelQuery, selected_batches
from freemocap.core.recording.sample_encoding.arrow_schema import SampleValidator


def check_cancelled(cancelled):
    if cancelled is not None and cancelled():
        raise CancelledError('Recording read cancelled')


@dataclass(frozen=True)
class ChannelArrays:
    context: ChannelSelection
    names: tuple[str, ...]
    components: tuple[str, ...]
    units: tuple[str, ...]
    frames: np.ndarray
    timestamps: np.ndarray
    values: np.ndarray
    present: np.ndarray
    source_components: tuple[str, ...] | None = None

    def to_data_tensor(
        self, *, scientific_provenance: ScientificProvenance,
        source_identity: SourceIdentity | None = None,
    ) -> DataTensor:
        """Bind saved channel identities without copying its numerical buffers.

        Owned arrays outlive the reader. Scratch-backed arrays have the lifetime
        of read_channel_arrays; publish an owned copy before leaving that context.
        """
        if source_identity is None:
            source_identity = SourceIdentity(source_id=self.context.source, sensor_group=self.context.sensor_group)
        if (source_identity.source_id != self.context.source
                or source_identity.sensor_group != self.context.sensor_group):
            raise ValueError("Tensor source identity disagrees with the saved channel")
        entity_axes = (
            AxisDefinition("entity_identity", self.names),
            AxisDefinition("component_identity", self.components if self.source_components is None else self.source_components),
        )
        tensor_axes = entity_axes if self.context.static else (AxisDefinition("sample_identity", self.frames), *entity_axes)
        layout = TensorLayout(axes=tensor_axes, dtype=self.values.dtype, component_units=self.units,
            reference_id=self.context.reference_frame, source_identity=source_identity, channel_kind=self.context.channel)
        presence = CompanionTensor(metadata_name="entry_presence", data_values=self.present,
                                   tensor_layout=TensorLayout(axes=tensor_axes, dtype=bool))
        return DataTensor(data_values=self.values, tensor_layout=layout,
                          scientific_provenance=scientific_provenance, companion_tensors=(presence,))

    def to_time_series(
        self, *, sample_timing: SampleTiming, scientific_provenance: ScientificProvenance,
        source_identity: SourceIdentity | None = None,
    ) -> TimeSeries:
        """Bind exact saved sampling; matching counts alone do not establish timing."""
        if self.context.static:
            raise ValueError("Static fits have no sample timing")
        if (not np.array_equal(self.frames, sample_timing.sample_ids)
                or not np.array_equal(self.timestamps, sample_timing.timestamps_s)):
            raise ValueError("Sample timing differs from saved channel IDs or timestamps")
        return TimeSeries(data_tensor=self.to_data_tensor(scientific_provenance=scientific_provenance,
                          source_identity=source_identity), sample_timing=sample_timing)

    def descriptor(self):
        return dict(context=self.context.model_dump(mode='json'), names=self.names,
            components=self.components, source_components=self.source_components or self.components,
            units=self.units, shape=list(self.values.shape),
            axes=['names', 'components'] if self.context.static else ['frames', 'names', 'components'],
            missing_values='NaN; present distinguishes recorded null from absent row')


@contextmanager
def read_channel_arrays(view: RecordingView, run_id: int, context: ChannelSelection, channel: Channel, *,
                        scratch: Path | None = None, max_resident_bytes: int | None = None,
                        components: tuple[str, ...] | None = None, static_values=None,
                        require_complete: bool = False, read_batches=None,
                        cancelled: Callable[[], bool] | None = None):
    """Assemble declared tensors in bounded batches without an output reorder copy.

    Without a resident-memory limit the output is owned RAM and outlives the view.
    With a limit, scratch-backed values/presence live only inside this context.
    Frame identities/timestamps are collected in memory; this is not a total memory
    bound. Strict saved reads also validate the complete declared trajectory grid.
    Component projection is explicit; authored ordering is the default.
    """
    components = tuple(channel.components) if components is None else components
    if (context.sensor_group, context.source, context.reference_frame, context.channel) != (
        channel.sensor_group, channel.source, channel.reference_frame, channel.kind
    ):
        raise ValueError('Channel selection differs from its declared identity')
    if len(components) != len(channel.components) or set(components) != set(channel.components):
        raise ValueError('Component order must cover the declared components exactly')
    if read_batches is None:
        query = ChannelQuery(run_id, context.sensor_group, context.source, context.channel, context.reference_frame)
        def read_batches(*, columns=None):
            yield from selected_batches(view, (query,), columns=columns, cancelled=cancelled)
    validator = None
    if require_complete:
        run = view.metadata.runs[run_id]
        selected_metadata = view.metadata.model_copy(update={
            'runs': {run_id: run.model_copy(update={'channels': (channel,)})}})
        validator = SampleValidator(metadata=selected_metadata)
    frame_parts, time_parts = [], []
    if not context.static:
        for batch in read_batches(columns=('frame_number', 'timestamp_s')):
            frame_column = batch.column('frame_number')
            batch_frames = frame_column.to_numpy(zero_copy_only=False)
            batch_times = batch.column('timestamp_s').to_numpy(zero_copy_only=False)
            if frame_column.null_count or np.any(batch_frames < 0) or not np.all(np.isfinite(batch_times)):
                raise ValueError('Invalid frame/time in recording source')
            unique_frames, reverse_first, reverse_inverse = np.unique(batch_frames if require_complete else batch_frames[::-1], return_index=True, return_inverse=True)
            last = reverse_first if require_complete else len(batch_frames) - 1 - reverse_first
            if np.any(batch_times != batch_times[last][reverse_inverse if require_complete else reverse_inverse[::-1]]):
                raise ValueError('Conflicting timestamps within a channel frame')
            frame_parts.append(unique_frames)
            time_parts.append(batch_times[last])
    if frame_parts:
        all_frames, all_times = np.concatenate(frame_parts), np.concatenate(time_parts)
        frames, reverse_first, reverse_inverse = np.unique(all_frames if require_complete else all_frames[::-1], return_index=True, return_inverse=True)
        times = all_times[reverse_first if require_complete else len(all_frames) - 1 - reverse_first]
        if np.any(all_times != times[reverse_inverse if require_complete else reverse_inverse[::-1]]):
            raise ValueError('Conflicting timestamps within a channel frame')
    else:
        frames, times = np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float64)
    if len(times) > 1 and np.any(np.diff(times) <= 0):
        raise ValueError('Channel timestamps must increase with frame numbers')
    if require_complete and len(frames) != view.metadata.runs[run_id].sensor_groups[channel.sensor_group].sample_count:
        raise ValueError("Point stream does not cover the declared frame grid")
    shape = (len(channel.names), len(components))
    if not context.static:
        shape = (len(frames), *shape)
    disk = max_resident_bytes is not None and int(np.prod(shape)) * 9 > max_resident_bytes
    if disk and scratch is None:
        raise ValueError('Disk-backed channel arrays require a scratch directory')
    storage = tempfile.TemporaryDirectory(prefix='arrays-', dir=scratch) if disk else nullcontext(None)
    with storage as temporary:
        def allocate(name, dtype, fill):
            array = (np.lib.format.open_memmap(Path(temporary) / name, mode='w+', dtype=dtype, shape=shape)
                     if disk else np.empty(shape, dtype=dtype))
            array.fill(fill)
            return array
        values, present = allocate('values.npy', np.float64, np.nan), allocate('present.npy', bool, False)
        try:
            names = {name: i for i, name in enumerate(channel.names)}
            axes = {name: i for i, name in enumerate(components)}
            if context.static:
                for name, row in static_values.items():
                    for component, value in row.items():
                        values[names[name], axes[component]] = value
                present.fill(True)
            else:
                declared_names = pa.array(channel.names, type=pa.string())
                declared_components = pa.array(components, type=pa.string())
                declared_units = pa.array([channel.components[c] for c in components], type=pa.string())
                flat_values, flat_present = values.reshape(-1), present.reshape(-1)
                for batch in read_batches():
                    if validator is not None:
                        validator.accept(batch=batch.replace_schema_metadata(None))
                    name_indices = pc.index_in(batch.column('name'), value_set=declared_names)
                    axis_indices = pc.index_in(batch.column('component'), value_set=declared_components)
                    if name_indices.null_count or axis_indices.null_count:
                        raise ValueError('Undeclared name/component or incorrect units in recording source')
                    units_match = pc.fill_null(pc.equal(batch.column('units'), pc.take(declared_units, axis_indices)), False)
                    if not pc.all(units_match).as_py():
                        raise ValueError('Undeclared name/component or incorrect units in recording source')
                    frame_indices = np.searchsorted(frames, batch.column('frame_number').to_numpy(zero_copy_only=False))
                    offsets = ((frame_indices * len(channel.names) + name_indices.to_numpy()) * len(components)
                               + axis_indices.to_numpy())
                    if np.unique(offsets).size != offsets.size or np.any(flat_present[offsets]):
                        raise ValueError('Duplicate sample/component in recording source')
                    value_column = batch.column('value')
                    batch_values = value_column.to_numpy(zero_copy_only=False)
                    if np.any(~np.isfinite(batch_values) & ~value_column.is_null().to_numpy(zero_copy_only=False)):
                        raise ValueError('Recording source requires finite numbers or nulls')
                    flat_present[offsets] = True
                    flat_values[offsets] = batch_values
            check_cancelled(cancelled)
            if validator is not None:
                validator.finish()
            yield ChannelArrays(context, channel.names, components, tuple(channel.components[c] for c in components),
                                frames, times, values, present, source_components=components)
        finally:
            for array in (values, present):
                if isinstance(array, np.memmap):
                    array._mmap.close()
