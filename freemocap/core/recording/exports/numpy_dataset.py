"""Compose declared recording channels into Forge scientific tensors for export."""
from contextlib import contextmanager
from dataclasses import replace
import json

import numpy as np

from skellyforge.core.data_tensors import (
    CompanionTensor, DefinitionDocument, RecordingDataset, SampleTiming,
    ScientificProvenance, SourceIdentity, TensorLayout, TimeSeries,
)
from freemocap.core.recording.exports.arrays import available_channels, MAX_RESIDENT_ARRAY_BYTES
from freemocap.core.recording.parquet_storage.channel_arrays import read_channel_arrays
from freemocap.core.recording.parquet_storage.channel_selection import ChannelSelection


def axis_definition(layout, name):
    return layout.axes[layout.axis_index(name)]


def scientific_selection(run, selected):
    """Expand the public pose projection and include its model's static outputs."""
    result = {}
    for item in selected:
        for native in item[2] if item[0].channel == 'SEGMENT_POSES' else (item,):
            result[native[0].key] = native
    model_sources = {(context.sensor_group, context.source) for context, _, _ in result.values()
                     if run.sources[context.source].definition.get('model_id') is not None}
    for item in available_channels(run):
        if item[0].static and (item[0].sensor_group, item[0].source) in model_sources:
            result[item[0].key] = item
    return tuple(result.values())


def declared_source(run, context):
    definition = run.sources[context.source].definition
    reference = run.reference_frames.get(context.reference_frame, {})
    camera_id = reference.get('camera_id', definition.get('camera_id'))
    if definition.get('camera_id') is not None and camera_id != definition['camera_id']:
        raise ValueError('Source and reference declare different camera identities')
    model_id = definition.get('model_id')
    if model_id is not None and model_id not in run.models:
        raise ValueError('Source declares an unavailable model definition')
    return SourceIdentity(source_id=context.source, sensor_group=context.sensor_group,
                          camera_id=camera_id, model_id=model_id)


def channel_definitions(metadata, run_id, selected):
    """Export scientific definitions, excluding pipeline execution configuration."""
    run = metadata.runs[run_id]
    documents = {}
    def retain(name, value):
        documents[name] = DefinitionDocument(name, json.dumps(value, ensure_ascii=False, allow_nan=False))
    retain('recording:context', dict(recording_id=metadata.recording_id, run_id=run_id,
        saved_presence='entry_presence means a recorded component row exists, including recorded null',
        saved_validity='No independent scientific validity mask is present in this recording schema',
        timing_identity='A channel-specific saved time series; group clock describes recorded seconds, not a hardware-clock claim',
        clock_epoch='Zero identifies this saved run; no hardware reset epoch is inferred'))
    public_source_fields = {'camera_id', 'video_filename', 'timing_method', 'nominal_fps', 'inferred_offset_s',
        'model_id', 'tracker', 'point_kind', 'scale_reference_name', 'landmark_names', 'segment_names',
        'detector_type', 'rtmpose_model_name', 'method', 'filter_config', 'triangulation_config',
        'tracker_config', 'rtmpose_confidence_threshold', 'mediapipe_model_complexity',
        'mediapipe_detection_confidence', 'mediapipe_presence_confidence', 'mediapipe_tracking_confidence',
        'mediapipe_num_hands', 'mediapipe_num_faces', 'body_alignment', 'anchor_segment_name',
        'charuco_tracking_enabled', 'charuco_board', 'board_mode', 'segment_origins',
        'segment_parents', 'joint_angle_names'}
    retained_sources = set()
    def retain_source(source_id):
        if source_id in retained_sources:
            return
        retained_sources.add(source_id)
        saved_source = run.sources[source_id]
        retain(f'source:{source_id}', dict(kind=str(saved_source.kind),
            definition={key: value for key, value in saved_source.definition.items() if key in public_source_fields}))
        upstream = saved_source.definition.get('tracker')
        if upstream is not None:
            if upstream not in run.sources:
                raise ValueError('Selected source names an unavailable upstream tracker')
            retain_source(upstream)
    for context, _, _ in selected:
        source = declared_source(run, context)
        retain_source(context.source)
        if source.camera_id is not None:
            for source_id, definition in run.sources.items():
                if definition.definition.get('camera_id') == source.camera_id:
                    retain_source(source_id)
        retain(f'sensor_group:{context.sensor_group}', run.sensor_groups[context.sensor_group].model_dump(mode='json'))
        if context.reference_frame is not None:
            retain(f'reference:{context.reference_frame}', run.reference_frames[context.reference_frame])
        if source.model_id is not None:
            retain(f'model:{source.model_id}', run.models[source.model_id].model_dump(mode='json'))
        for saved_fit in run.scale_fits:
            if (saved_fit.sensor_group, saved_fit.source) == (context.sensor_group, context.source):
                retain(f'fit_inputs:{context.sensor_group}:{context.source}', dict(
                    inputs=saved_fit.inputs.model_dump(mode='json'), reference_frame=saved_fit.reference_frame,
                    units=saved_fit.units))
    return tuple(documents.values())


@contextmanager
def saved_channel_tensor(view, run_id, item, *, source_hash, scratch, cancelled=None):
    """Borrow one authored channel until both NumPy writers finish consuming it."""
    context, channel, static_values = item
    run = view.metadata.runs[run_id]
    source = declared_source(run, context)
    provenance = ScientificProvenance(
        meaning='saved_model_output' if source.model_id is not None else 'saved_processing_output',
        operation_id=f'saved_stage:{channel.stage}', input_refs=(f'parquet_sha256:{source_hash}',), model_id=source.model_id)
    with read_channel_arrays(view, run_id, context, channel, static_values=static_values,
            scratch=scratch, max_resident_bytes=MAX_RESIDENT_ARRAY_BYTES, cancelled=cancelled) as arrays:
        tensor = arrays.to_data_tensor(scientific_provenance=provenance, source_identity=source)
        if context.static and context.channel in {'SEGMENT_SCALES', 'SEGMENT_LENGTHS'}:
            saved_fit = next((fit for fit in run.scale_fits if fit.fit is not None
                and (fit.sensor_group, fit.source) == (context.sensor_group, context.source)), None)
            if saved_fit is not None:
                support_layout = TensorLayout((axis_definition(tensor.tensor_layout, 'entity_identity'),), bool)
                names = np.asarray(arrays.names)
                companions = tuple(CompanionTensor(label, np.isin(names, tuple(identifiers)), support_layout)
                    for label, identifiers in (('measured_support', saved_fit.fit.measured_segment_names),
                                                ('voting_support', saved_fit.fit.voting_segment_names)))
                tensor = replace(tensor, companion_tensors=(*tensor.companion_tensors, *companions))
        if context.static:
            yield tensor
        else:
            # The saved schema declares group-relative seconds but no hardware
            # clock ID/reset counter. Scope identities to this recording run;
            # never merge channels because their numeric timestamps happen to match.
            timing = SampleTiming(timeline_id=f'{view.metadata.recording_id}:run:{run_id}:channel:{context.key}',
                clock_id=f'{view.metadata.recording_id}:run:{run_id}:group:{context.sensor_group}',
                source_identity=source, sample_ids=arrays.frames, timestamps_s=arrays.timestamps)
            yield TimeSeries(tensor, timing)


def runtime_channels(dataset, *, metadata, run_id, selected):
    """Validate selected runtime identities without rereading Parquet values."""
    if not isinstance(dataset, RecordingDataset):
        raise TypeError('runtime_dataset must be a Forge RecordingDataset')
    if dataset.recording_id != metadata.recording_id or dataset.run_id != run_id:
        raise ValueError('Runtime dataset recording/run identity differs from the export')
    run = metadata.runs[run_id]
    expected = {context.key: (context, channel) for context, channel, _ in selected}
    result = {}
    for data in (*dataset.time_series, *dataset.static_tensors):
        tensor = data.data_tensor if isinstance(data, TimeSeries) else data
        layout = tensor.tensor_layout
        source = layout.source_identity
        context = ChannelSelection(sensor_group=source.sensor_group, source=source.source_id,
            reference_frame=layout.reference_id, channel=layout.channel_kind, static=not isinstance(data, TimeSeries))
        if context.key not in expected:
            raise ValueError('Runtime dataset contains an unselected scientific channel')
        declared_context, channel = expected[context.key]
        if source != declared_source(run, declared_context):
            raise ValueError('Runtime source identity differs from the declared recording source')
        if (axis_definition(layout, 'entity_identity').identifiers != channel.names
                or axis_definition(layout, 'component_identity').identifiers != tuple(channel.components)
                or layout.component_units != tuple(channel.components.values())):
            raise ValueError('Runtime channel layout differs from the declared recording channel')
        result[context.key] = data
    if set(result) != set(expected):
        raise ValueError('Runtime dataset does not contain every selected scientific channel/static fit')
    return result


def tensor_description(context, data):
    tensor = data.data_tensor if isinstance(data, TimeSeries) else data
    layout = tensor.tensor_layout
    result = dict(context=context.model_dump(mode='json'), names=axis_definition(layout, 'entity_identity').identifiers,
        components=axis_definition(layout, 'component_identity').identifiers, source_components=axis_definition(layout, 'component_identity').identifiers,
        units=layout.component_units, shape=list(tensor.data_values.shape), axes=[axis.axis_name for axis in layout.axes],
        missing_values='See explicit companion tensors; recorded null and absent entries are distinct')
    if isinstance(data, TimeSeries):
        timing = data.sample_timing
        result['timing'] = dict(frame_count=data.sample_count, timeline_id=timing.timeline_id,
            clock_id=timing.clock_id, first_frame=int(timing.sample_ids[0]) if data.sample_count else None,
            last_frame=int(timing.sample_ids[-1]) if data.sample_count else None,
            first_timestamp_s=float(timing.timestamps_s[0]) if data.sample_count else None,
            last_timestamp_s=float(timing.timestamps_s[-1]) if data.sample_count else None)
    return result
