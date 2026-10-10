"""Ordered scientific arrays from one open recording snapshot; no resampling."""
from collections.abc import Callable
from concurrent.futures import CancelledError
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import tempfile

import numpy as np
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


def channel_batches(view, run_id, context, cancelled):
    for batch in view.parquet.iter_batches(batch_size=65536):
        check_cancelled(cancelled)
        mask = pc.equal(batch.column('run_id'), run_id)
        for field, value in (('sensor_group', context.sensor_group), ('source', context.source),
                             ('channel', context.channel), ('reference_frame', context.reference_frame)):
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
    clock = {}
    if not context.static:
        for batch in channel_batches(view, run_id, context, cancelled):
            timing = batch.select(['frame_number', 'timestamp_s']).to_pydict()
            for frame, timestamp in zip(timing['frame_number'], timing['timestamp_s'], strict=True):
                if frame is None or frame < 0 or timestamp is None or not np.isfinite(timestamp):
                    raise ValueError('Invalid frame/time in export source')
                if frame in clock and clock[frame] != timestamp:
                    raise ValueError('Conflicting timestamps within a channel frame')
                clock[frame] = timestamp
    frames = np.array(sorted(clock), dtype=np.int64)
    times = np.array([clock[int(f)] for f in frames], dtype=np.float64)
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
            frame_indices = {int(frame): i for i, frame in enumerate(frames)}
            if context.static:
                for name, row in static_values.items():
                    for component, value in row.items():
                        values[names[name], axes[component]] = value
                present.fill(True)
            else:
                for batch in channel_batches(view, run_id, context, cancelled):
                    rows = batch.select(['frame_number', 'name', 'component', 'units', 'value']).to_pydict()
                    for frame, name, component, unit, value in zip(*rows.values(), strict=True):
                        if name not in names or component not in axes or channel.components[component] != unit:
                            raise ValueError('Undeclared name/component or incorrect units in export source')
                        index = (frame_indices[frame], names[name], axes[component])
                        if present[index]:
                            raise ValueError('Duplicate sample/component in export source')
                        if value is not None and not np.isfinite(value):
                            raise ValueError('Export source requires finite numbers or nulls')
                        present[index] = True
                        values[index] = np.nan if value is None else value
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
