"""Ordered scientific arrays from one open recording snapshot; no resampling."""
from collections.abc import Callable
from concurrent.futures import CancelledError
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import tempfile

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from freemocap.core.recording.parquet_storage.parquet_reader import read_static_channels
from freemocap.core.recording.parquet_storage.recording_view import RecordingView


from freemocap.core.recording.exports.requests import ChannelSelection, ScientificExportRequest

MAX_RESIDENT_ARRAY_BYTES = 64 * 1024 * 1024


def available_channels(run):
    return [(ChannelSelection(sensor_group=c.sensor_group, source=c.source,
                reference_frame=c.reference_frame, channel=str(c.kind), static=static), c, values)
            for static, c, values in [(False, c, None) for c in run.channels]
            + [(True, item.channel, item.values) for item in read_static_channels(run)]]


def scientific_channels(run):
    """User-facing data products; segment poses pair saved positions and rotations."""
    available = available_channels(run)
    result = [item for item in available if item[0].channel in
              {'LANDMARKS_3D', 'RAW_KEYPOINTS_3D', 'KEYPOINTS_3D', 'OVERLAY_2D'} and not item[0].static]
    for context, channel, _ in available:
        if context.channel != 'SEGMENT_ORIGINS':
            continue
        rotation = next((item for item in available if item[0] == context.model_copy(update={'channel': 'ROTATIONS_WORLD'})), None)
        if rotation is not None and channel.names == rotation[1].names:
            pose = context.model_copy(update={'channel': 'SEGMENT_POSES'})
            descriptor = SimpleNamespace(names=channel.names, components={
                **{axis: channel.components[axis] for axis in ('x', 'y', 'z')},
                **{axis: '1' for axis in ('qw', 'qx', 'qy', 'qz')}})
            result.append((pose, descriptor, ((context, channel, None), rotation)))
    return result


def resolve_selection(view: RecordingView, request: ScientificExportRequest):
    if request.expected_revision is not None and request.expected_revision != view.revision:
        raise ValueError('Recording revision changed; reload the saved result')
    run_id = view.metadata.selected_run_id if request.run_id is None else request.run_id
    if run_id not in view.metadata.runs:
        raise ValueError(f'Unknown recording run: {run_id}')
    if not request.formats:
        raise ValueError('Choose at least one export format')
    available = (available_channels(view.metadata.runs[run_id]) if request.wide_csv is not None
                 else scientific_channels(view.metadata.runs[run_id]))
    selected = set(request.wide_csv) if request.wide_csv is not None else {item[0] for item in available if item[0].channel in request.data}
    if request.wide_csv is None and set(request.data) - {item[0].channel for item in available}:
        raise ValueError('Selected data is unavailable in this run; update the export selection')
    unknown = selected - {item[0] for item in available}
    if unknown or not selected:
        raise ValueError(f'No channels selected or unavailable channel selection: {unknown}')
    return run_id, [item for item in available if item[0] in selected]


def check_cancelled(cancelled):
    if cancelled is not None and cancelled():
        raise CancelledError('Scientific export cancelled')


def channel_batches(view, run_id, context, cancelled, *, columns=None):
    filters = (('run_id', run_id), ('sensor_group', context.sensor_group), ('source', context.source),
               ('channel', context.channel), ('reference_frame', context.reference_frame))
    if columns is not None:
        columns = list(dict.fromkeys((*columns, *(field for field, _ in filters))))
    # Saved files contain many different channels. Skip a row group only when
    # its statistics prove it cannot match; missing statistics always fall back
    # to decoding and filtering. Keep the caller's open snapshot throughout.
    row_groups = []
    schema = view.parquet.schema_arrow
    filter_columns = tuple((schema.get_field_index(field), value) for field, value in filters)
    for index in range(view.parquet.num_row_groups):
        check_cancelled(cancelled)
        group = view.parquet.metadata.row_group(index)
        excluded = False
        for column_index, value in filter_columns:
            statistics = group.column(column_index).statistics
            if statistics is None:
                continue
            if value is None:
                excluded = statistics.null_count == 0
            else:
                excluded = (statistics.null_count == group.num_rows or
                            (statistics.has_min_max and not statistics.min <= value <= statistics.max))
            if excluded:
                break
        if not excluded:
            row_groups.append(index)
    for batch in view.parquet.iter_batches(batch_size=65536, columns=columns, row_groups=row_groups):
        check_cancelled(cancelled)
        mask = pc.equal(batch.column('run_id'), run_id)
        for field, value in filters[1:]:
            column = batch.column(field)
            mask = pc.and_(mask, pc.is_null(column) if value is None else pc.fill_null(pc.equal(column, value), False))
        result = batch.filter(mask)
        if result.num_rows:
            yield result


@dataclass
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

    def descriptor(self):
        return dict(context=self.context.model_dump(mode='json'), names=self.names,
            components=self.components, source_components=self.source_components or self.components,
            units=self.units, shape=list(self.values.shape),
            axes=['names', 'components'] if self.context.static else ['frames', 'names', 'components'],
            missing_values='NaN; present distinguishes recorded null from absent row')


@contextmanager
def ordered_arrays(view: RecordingView, run_id: int, item, *, scratch: Path,
                   cancelled: Callable[[], bool] | None = None):
    """At most one channel resident; large value/presence arrays are disk backed.

    Frames are the sorted union observed in this context, never inferred from FPS.
    A completely absent frame has no invented timestamp. Names follow the descriptor.
    """
    context, channel, static_values = item
    if context.channel == 'SEGMENT_POSES':
        with ordered_arrays(view, run_id, static_values[0], scratch=scratch, cancelled=cancelled) as positions:
            with ordered_arrays(view, run_id, static_values[1], scratch=scratch, cancelled=cancelled) as rotations:
                if not np.array_equal(positions.frames, rotations.frames) or not np.array_equal(positions.timestamps, rotations.timestamps):
                    raise ValueError('Segment positions and rotations have different saved frame grids')
                yield ChannelArrays(context, channel.names, tuple(channel.components), tuple(channel.components.values()),
                    positions.frames, positions.timestamps, np.concatenate((positions.values, rotations.values), axis=-1),
                    np.concatenate((positions.present, rotations.present), axis=-1))
        return
    components = tuple(channel.components)
    if set(components) == {'x', 'y', 'z'}:
        components = ('x', 'y', 'z')
    elif set(components) == {'w', 'x', 'y', 'z'}:
        components = ('w', 'x', 'y', 'z')
    frame_parts, time_parts = [], []
    if not context.static:
        for batch in channel_batches(view, run_id, context, cancelled, columns=('frame_number', 'timestamp_s')):
            frame_column = batch.column('frame_number')
            batch_frames = frame_column.to_numpy(zero_copy_only=False)
            batch_times = batch.column('timestamp_s').to_numpy(zero_copy_only=False)
            if frame_column.null_count or np.any(batch_frames < 0) or not np.all(np.isfinite(batch_times)):
                raise ValueError('Invalid frame/time in export source')
            unique_frames, reverse_first, reverse_inverse = np.unique(batch_frames[::-1], return_index=True, return_inverse=True)
            last = len(batch_frames) - 1 - reverse_first
            if np.any(batch_times != batch_times[last][reverse_inverse[::-1]]):
                raise ValueError('Conflicting timestamps within a channel frame')
            frame_parts.append(unique_frames)
            time_parts.append(batch_times[last])
    if frame_parts:
        all_frames, all_times = np.concatenate(frame_parts), np.concatenate(time_parts)
        frames, reverse_first, reverse_inverse = np.unique(all_frames[::-1], return_index=True, return_inverse=True)
        times = all_times[len(all_frames) - 1 - reverse_first]
        if np.any(all_times != times[reverse_inverse[::-1]]):
            raise ValueError('Conflicting timestamps within a channel frame')
    else:
        frames, times = np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float64)
    if len(times) > 1 and np.any(np.diff(times) <= 0):
        raise ValueError('Channel timestamps must increase with frame numbers')
    shape = (len(channel.names), len(components))
    if not context.static:
        shape = (len(frames), *shape)
    with tempfile.TemporaryDirectory(prefix='arrays-', dir=scratch) as temporary:
        disk = int(np.prod(shape)) * 9 > MAX_RESIDENT_ARRAY_BYTES
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
                for batch in channel_batches(view, run_id, context, cancelled):
                    name_indices = pc.index_in(batch.column('name'), value_set=declared_names)
                    axis_indices = pc.index_in(batch.column('component'), value_set=declared_components)
                    if name_indices.null_count or axis_indices.null_count:
                        raise ValueError('Undeclared name/component or incorrect units in export source')
                    units_match = pc.fill_null(pc.equal(batch.column('units'), pc.take(declared_units, axis_indices)), False)
                    if not pc.all(units_match).as_py():
                        raise ValueError('Undeclared name/component or incorrect units in export source')
                    frame_indices = np.searchsorted(frames, batch.column('frame_number').to_numpy(zero_copy_only=False))
                    offsets = ((frame_indices * len(channel.names) + name_indices.to_numpy()) * len(components)
                               + axis_indices.to_numpy())
                    if np.unique(offsets).size != offsets.size or np.any(flat_present[offsets]):
                        raise ValueError('Duplicate sample/component in export source')
                    value_column = batch.column('value')
                    batch_values = value_column.to_numpy(zero_copy_only=False)
                    if np.any(~np.isfinite(batch_values) & ~value_column.is_null().to_numpy(zero_copy_only=False)):
                        raise ValueError('Export source requires finite numbers or nulls')
                    flat_present[offsets] = True
                    flat_values[offsets] = batch_values
            check_cancelled(cancelled)
            exported_components = tuple(
                'confidence' if context.channel == 'OVERLAY_2D' and c == 'visibility' else c
                for c in components)
            if len(set(exported_components)) != len(exported_components):
                raise ValueError('Export component aliases must be unique')
            yield ChannelArrays(context, channel.names, exported_components, tuple(channel.components[c] for c in components),
                                frames, times, values, present, source_components=components)
        finally:
            for array in (values, present):
                if isinstance(array, np.memmap):
                    array._mmap.close()
