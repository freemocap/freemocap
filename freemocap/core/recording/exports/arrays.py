"""Ordered scientific arrays from one open recording snapshot; no resampling."""
from collections.abc import Callable
from concurrent.futures import CancelledError
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from freemocap.core.recording.parquet_storage.parquet_reader import read_static_channels
from freemocap.core.recording.parquet_storage.recording_view import RecordingView
from freemocap.core.recording.parquet_storage.selected_batches import ChannelQuery, selected_batches
from freemocap.core.recording.parquet_storage.channel_arrays import ChannelArrays, read_channel_arrays


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
    query = ChannelQuery(run_id=run_id, sensor_group=context.sensor_group,
        source=context.source, channel_kind=context.channel, reference_frame=context.reference_frame)
    yield from selected_batches(view, (query,),
        columns=None if columns is None else tuple(columns), cancelled=cancelled)


@contextmanager
def ordered_arrays(view: RecordingView, run_id: int, item, *, scratch: Path,
                   cancelled: Callable[[], bool] | None = None):
    """Export projection over shared arrays; canonical labels stay export-owned."""
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
    def read_batches(*, columns=None):
        return channel_batches(view, run_id, context, cancelled, columns=columns)
    with read_channel_arrays(view, run_id, context, channel, components=components,
            static_values=static_values, scratch=scratch, max_resident_bytes=MAX_RESIDENT_ARRAY_BYTES,
            read_batches=read_batches, cancelled=cancelled) as result:
        exported_components = tuple('confidence' if context.channel == 'OVERLAY_2D' and c == 'visibility' else c
                                    for c in components)
        if len(set(exported_components)) != len(exported_components):
            raise ValueError('Export component aliases must be unique')
        yield replace(result, components=exported_components)
