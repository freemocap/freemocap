"""LSL projection must preserve acquisition identity, values and declared schema."""
from dataclasses import FrozenInstanceError
import math

import pytest

from freemocap.core.streaming.outputs.lsl_clock import LslClockMapping


def test_clock_mapping_uses_measurement_instant_despite_known_processing_delay():
    source_ns = 12_345_678_901_234_567
    original_camera_ns = (('camera-A', source_ns - 6), ('camera-B', source_ns + 6))
    # The clocks have different epochs. Calibration is three seconds after capture.
    mapping = LslClockMapping(source_ns + 3_000_000_000, 4003.25, 20)
    expected_measurement_time = 4000.25
    # Deliver the same source after arbitrary processing/queue delays; no clock
    # callback or observed delivery time enters conversion.
    for delivery_delay_s in (0.0, 0.5, 9.0, 120.0):
        pretend_delivery_time = expected_measurement_time + delivery_delay_s
        result = mapping.to_lsl_seconds(source_ns)
        assert result == expected_measurement_time
        if delivery_delay_s:
            assert result != pretend_delivery_time
    assert original_camera_ns == (('camera-A', 12_345_678_901_234_561),
                                  ('camera-B', 12_345_678_901_234_573))
    assert source_ns == 12_345_678_901_234_567


def test_integer_difference_is_preserved_above_float_integer_precision():
    anchor = 2**56 + 17
    mapping = LslClockMapping(anchor, 10.0)
    assert mapping.to_lsl_seconds(anchor + 1) == pytest.approx(10.000000001, abs=1e-15)
    assert mapping.to_lsl_seconds(anchor + 1) != mapping.to_lsl_seconds(anchor)


def test_clock_calibration_selects_narrowest_bracket_and_stays_immutable():
    perf_observations = iter((100, 180, 200, 204, 300, 340))
    lsl_observations = iter((20.0, 21.0, 22.0))
    mapping = LslClockMapping.calibrate(lambda: next(lsl_observations),
        perf_counter_ns=lambda: next(perf_observations), observations=3)
    assert mapping.perf_counter_anchor_ns == 202
    assert mapping.lsl_anchor_s == 21.0
    assert mapping.calibration_span_ns == 4
    with pytest.raises(FrozenInstanceError):
        mapping.lsl_anchor_s = 99.0


@pytest.mark.parametrize('timestamp', [-1, math.nan, math.inf, -math.inf, True])
def test_invalid_acquisition_timestamps_fail(timestamp):
    with pytest.raises(ValueError):
        LslClockMapping(100, 20.0).to_lsl_seconds(timestamp)


def test_reversed_clock_calibration_fails():
    samples = iter((100, 99))
    with pytest.raises(ValueError, match='bracket'):
        LslClockMapping.calibrate(lambda: 1.0, perf_counter_ns=lambda: next(samples), observations=1)


import json
import os
from dataclasses import replace

import numpy as np
from pydantic import ValidationError

from freemocap.core.streaming.message_model import (
    ChannelBlock, ChannelKind, FrameMessage, ModelInstance, MessageEnvelope,
)
from freemocap.core.streaming.outputs.contracts import OutputSample
from freemocap.core.streaming.outputs.lsl import LslConfig, LslEmitter


class XmlElement:
    def __init__(self):
        self.values = {}
        self.children = []

    def append_child_value(self, name, value):
        self.values[name] = value
        return self

    def append_child(self, name):
        child = XmlElement()
        self.children.append((name, child))
        return child


class FakeInfo:
    def __init__(self, **kwargs):
        self.parameters = kwargs
        self.xml = XmlElement()

    def desc(self):
        return self.xml


class FakeOutlet:
    def __init__(self, record):
        self.record = record

    def have_consumers(self):
        return self.record.get("consumers", True)

    def push_sample(self, values, *, timestamp):
        if self.record.get('fail_push'):
            raise RuntimeError('Independent receiver transport failed')
        # Capture the public library boundary, independent of the decoder/schema.
        self.record['samples'].append((list(values), timestamp))

    def __del__(self):
        self.record['destroyed'] = True


class FakeLsl:
    def __init__(self):
        self.records = []

    StreamInfo = FakeInfo

    def StreamOutlet(self, info, **kwargs):
        record = {'info': info, 'options': kwargs, 'samples': [], 'destroyed': False}
        self.records.append(record)
        return FakeOutlet(record)


def sample_frame(*, frame_number=0, source_ns=1_000_000_000_000_000,
                 values=(1.25, float('nan'), -3.5), statuses=b'\x02'):
    block = ChannelBlock(kind=ChannelKind.LANDMARKS_3D, columns=('x', 'y', 'z'),
        names=('head',), data=np.asarray(values, dtype='<f4').tobytes(),
        sample_status=statuses,
        status_labels=('unavailable', 'current_input', 'predicted_support', 'retained_value') if statuses is not None else None)
    frame = FrameMessage(envelope=MessageEnvelope(timestamp=float(source_ns)),
        frame_number=frame_number,
        instances=(ModelInstance(instance_id=0, model_id='test-model', channels=(block,)),))
    return OutputSample(frame, 'pipeline-A', source_ns,
        (('camera-1', int(source_ns) - 1), ('camera-2', int(source_ns) + 1)))


def emitter_for(sample):
    backend = FakeLsl()
    clock = LslClockMapping(int(sample.source_timestamp_ns), 321.125, 40)
    return LslEmitter(LslConfig(), backend=backend, clock=clock), backend


def test_values_status_metadata_and_exact_ns_provenance_share_capture_time():
    source_ns = 2**56 + 13
    sample = sample_frame(source_ns=source_ns)
    emitter, backend = emitter_for(sample)
    emitter.emit(sample)
    numeric, provenance = backend.records
    values, timestamp = numeric['samples'][0]
    np.testing.assert_equal(values, [1.25, np.nan, -3.5, 2.0])
    assert timestamp == 321.125
    info = numeric['info']
    assert info.parameters['channel_format'] == 'float32'
    assert info.parameters['channel_count'] == 4
    assert info.parameters['nominal_srate'] == 0.0
    channels = info.xml.children[0][1].children
    assert [node.values['label'] for _, node in channels] == [
        'head.x', 'head.y', 'head.z', 'head.sample_status']
    assert [node.values['unit'] for _, node in channels] == ['mm', 'mm', 'mm', 'status_code']
    metadata = json.loads(info.xml.values['freemocap_metadata'])
    assert metadata['sample_status_labels'][2] == 'predicted_support'
    assert metadata['row_names'] == ['head']
    assert provenance['samples'][0][1] == timestamp
    exact = json.loads(provenance['samples'][0][0][0])
    assert exact['source_timestamp_ns'] == str(source_ns)
    assert exact['camera_timestamps_ns'] == {'camera-1': str(source_ns - 1), 'camera-2': str(source_ns + 1)}
    assert sample.source_timestamp_ns == source_ns
    assert sample.camera_timestamps_ns == (('camera-1', source_ns - 1), ('camera-2', source_ns + 1))
    emitter.close()
    assert all(record['destroyed'] for record in backend.records)


def test_cached_stream_reports_source_frame_gaps_and_preserves_unchanged_values():
    sample = sample_frame()
    emitter, backend = emitter_for(sample)
    emitter.emit(sample)
    next_sample = replace(sample, frame=replace(sample.frame, frame_number=4),
        source_timestamp_ns=sample.source_timestamp_ns + 100_000_000)
    emitter.emit(next_sample)
    assert len(backend.records) == 2
    provenance = json.loads(backend.records[1]['samples'][-1][0][0])
    assert provenance['source_frame_gap'] == 3
    assert backend.records[0]['samples'][-1][1] == pytest.approx(321.225)
    emitter.close()


def test_pipeline_rollover_releases_old_outlets_and_bounds_active_storage():
    sample = sample_frame(frame_number=20)
    emitter, backend = emitter_for(sample)
    try:
        emitter.emit(sample)
        # Include a return to the original ID: this is a new discovery lifetime,
        # not continuation of its retired schema or frame-number cursor.
        for pipeline_id in [f'pipeline-{index}' for index in range(20)] + [sample.pipeline_id]:
            emitter.emit(replace(sample, pipeline_id=pipeline_id,
                frame=replace(sample.frame, frame_number=0)))
            assert all(record['destroyed'] for record in backend.records[:-2])
            assert not any(record['destroyed'] for record in backend.records[-2:])
            assert len(emitter._channels) == 1
            assert set(emitter._provenance) == {pipeline_id}
            assert set(emitter._topologies) == {pipeline_id}
            assert emitter._last_frames == {pipeline_id: 0}
            provenance = json.loads(backend.records[-1]['samples'][0][0][0])
            assert provenance['source_frame_gap'] == 0
        identities = [record['info'].parameters['source_id'] for record in backend.records]
        assert len(set(identities)) == len(identities)
    finally:
        emitter.close()
    assert all(record['destroyed'] for record in backend.records)
    assert not any((emitter._channels, emitter._provenance, emitter._topologies, emitter._last_frames))


def test_shape_change_fails_before_any_new_sample_is_sent():
    sample = sample_frame()
    emitter, backend = emitter_for(sample)
    emitter.emit(sample)
    block = sample.frame.instances[0].channels[0]
    changed = replace(block, names=('head', 'pelvis'), data=block.data * 2,
        sample_status=b'\x01\x02')
    owner = replace(sample.frame.instances[0], channels=(changed,))
    new_frame = replace(sample.frame, frame_number=1, instances=(owner,))
    with pytest.raises(ValueError, match='schema changed'):
        emitter.emit(replace(sample, frame=new_frame))
    assert [len(record['samples']) for record in backend.records] == [1, 1]
    emitter.close()


def test_missing_channel_coverage_and_invalid_status_fail_clearly():
    sample = sample_frame()
    emitter, backend = emitter_for(sample)
    emitter.emit(sample)
    missing = replace(sample.frame, frame_number=1, instances=())
    emitter.emit(replace(sample, frame=missing))
    coverage = json.loads(backend.records[1]['samples'][-1][0][0])
    assert coverage['available_channel_identities'] == []
    assert len(coverage['absent_channel_identities']) == 1
    invalid = sample_frame(frame_number=2, statuses=b'\xff')
    with pytest.raises(ValueError, match='status'):
        emitter.emit(invalid)
    assert len(backend.records[0]['samples']) == 1
    emitter.close()


def test_no_timestamp_zero_sentinel_or_out_of_order_sample_is_published():
    sample = sample_frame()
    backend = FakeLsl()
    emitter = LslEmitter(LslConfig(), backend=backend,
        clock=LslClockMapping(int(sample.source_timestamp_ns), 0.0))
    with pytest.raises(ValueError, match='sentinel'):
        emitter.emit(sample)
    assert backend.records == []
    emitter.close()
    emitter, backend = emitter_for(sample)
    emitter.emit(sample)
    with pytest.raises(ValueError, match='order'):
        emitter.emit(sample)
    emitter.close()
    emitter.close()
    with pytest.raises(RuntimeError, match='closed'):
        emitter.emit(sample)


def test_transport_failure_propagates_and_close_releases_owned_outlets():
    sample = sample_frame()
    emitter, backend = emitter_for(sample)
    emitter.emit(sample)
    backend.records[0]['fail_push'] = True
    with pytest.raises(RuntimeError, match='transport failed'):
        emitter.emit(replace(sample, frame=replace(sample.frame, frame_number=1)))
    assert len(backend.records[1]['samples']) == 1
    emitter.close()
    assert all(record['destroyed'] for record in backend.records)


def test_lsl_config_rejects_unknown_fields_and_empty_filters():
    with pytest.raises(ValidationError):
        LslConfig(send_timestamp=True)
    with pytest.raises(ValidationError):
        LslConfig(channel_kinds=())


def test_two_outputs_use_distinct_source_identities():
    sample = sample_frame()
    first, backend1 = emitter_for(sample)
    second, backend2 = emitter_for(sample)
    first.emit(sample)
    second.emit(sample)
    assert backend1.records[0]['info'].parameters['source_id'] != backend2.records[0]['info'].parameters['source_id']
    first.close()
    assert all(record['destroyed'] for record in backend1.records)
    assert not any(record['destroyed'] for record in backend2.records)
    second.close()


def test_actual_pixel_length_units_are_preserved_and_unit_changes_fail():
    from freemocap.core.diagnostics.pipeline_diagnostics import PipelineDiagnostics
    sample = sample_frame()
    pixel_frame = replace(sample.frame, diagnostics=PipelineDiagnostics('pixels', (), {}))
    sample = replace(sample, frame=pixel_frame)
    emitter, backend = emitter_for(sample)
    emitter.emit(sample)
    channels = backend.records[0]['info'].xml.children[0][1].children
    assert [node.values['unit'] for _, node in channels][:3] == ['pixels'] * 3
    metric_frame = replace(sample.frame, frame_number=1,
        diagnostics=PipelineDiagnostics('millimeters', (), {}))
    with pytest.raises(ValueError, match='schema changed'):
        emitter.emit(replace(sample, frame=metric_frame))
    emitter.close()


@pytest.mark.asyncio
async def test_shared_manager_lsl_idle_start_scoped_failure_and_cleanup():
    import asyncio
    from freemocap.core.streaming.outputs.contracts import ProtocolDefinition, SourceBatch, StartOutputRequest
    from freemocap.core.streaming.outputs.manager import StreamingOutputManager

    class Source:
        batch = SourceBatch()

        def source_ids(self):
            return self.batch.active_sources

        def poll(self):
            return self.batch

    source = Source()
    backends = []

    def create(config):
        backend = FakeLsl()
        backends.append(backend)
        return LslEmitter(config, backend=backend, clock=LslClockMapping(0, 100.0))

    manager = StreamingOutputManager(source=source,
        protocols=(ProtocolDefinition('lsl', LslConfig, create, 'fail'),))

    async def wait_until(predicate):
        for _ in range(1000):
            if predicate():
                return
            await asyncio.sleep(0.01)
        raise AssertionError(f'Output state did not settle within the test deadline: {manager.list_outputs()}')

    try:
        first = await manager.start(StartOutputRequest(protocol='lsl'))
        second = await manager.start(StartOutputRequest(protocol='lsl'))
        assert first.status == second.status == 'idle'
        assert backends[0].records == backends[1].records == []
        sample = sample_frame()
        source.batch = SourceBatch(samples=(sample,), active_sources=('pipeline-A',))
        await wait_until(lambda: all(manager.get(key).frames_before_ready == 1 for key in (first.id, second.id)))
        sample = replace(sample, frame=replace(sample.frame, frame_number=1),
                         source_timestamp_ns=sample.source_timestamp_ns + 1_000_000)
        source.batch = SourceBatch(samples=(sample,), active_sources=('pipeline-A',))
        await wait_until(lambda: all(manager.get(key).frames_emitted == 1 for key in (first.id, second.id)))
        backends[0].records[0]['fail_push'] = True
        source.batch = SourceBatch(samples=(replace(sample,
            frame=replace(sample.frame, frame_number=2),
            source_timestamp_ns=sample.source_timestamp_ns + 1_000_000),), active_sources=('pipeline-A',))
        await wait_until(lambda: manager.get(first.id).status == 'failed'
            and manager.get(second.id).frames_emitted == 2)
        assert 'transport failed' in manager.get(first.id).error
        assert manager.get(second.id).status == 'running'
        assert (await manager.stop(first.id)).status == 'stopped'
        assert (await manager.stop(second.id)).status == 'stopped'
        assert all(record['destroyed'] for backend in backends for record in backend.records)
    finally:
        await manager.aclose()


@pytest.mark.skipif(not os.environ.get('FREEMOCAP_LSL_REFERENCE_PARQUET'),
                   reason='Set FREEMOCAP_LSL_REFERENCE_PARQUET for independent reference-data evidence')
def test_reference_recording_numeric_values_and_sample_grid():
    import pyarrow.parquet as pq
    table = pq.read_table(os.environ['FREEMOCAP_LSL_REFERENCE_PARQUET'],
        filters=[('channel', '=', 'LANDMARKS_3D'), ('frame_number', '<', 3)],
        columns=['timestamp_s', 'frame_number', 'source', 'name', 'component', 'value'])
    rows = table.to_pylist()
    assert rows
    source = rows[0]['source']
    # This recording's grid is relative time. The explicitly chosen replay
    # anchor maps the stored grid; it is not claimed as original hardware ns.
    backend = FakeLsl()
    emitter = LslEmitter(LslConfig(), backend=backend, clock=LslClockMapping(0, 1000.0))
    expected = []
    for frame_number in sorted({row['frame_number'] for row in rows}):
        frame_rows = [row for row in rows if row['source'] == source and row['frame_number'] == frame_number]
        names = tuple(dict.fromkeys(row['name'] for row in frame_rows))
        components = tuple(dict.fromkeys(row['component'] for row in frame_rows))
        lookup = {(row['name'], row['component']): row['value'] for row in frame_rows}
        values = np.asarray([lookup[(name, component)] for name in names for component in components], dtype='<f4')
        block = ChannelBlock(ChannelKind.LANDMARKS_3D, components, values.tobytes(), names=names)
        frame = FrameMessage(frame_number=frame_number,
            instances=(ModelInstance(0, 'reference', (block,)),))
        recorded_seconds = frame_rows[0]['timestamp_s']
        emitter.emit(OutputSample(frame, 'replay-reference', recorded_seconds * 1e9))
        expected.append((values.copy(), len(names), 1000.0 + recorded_seconds))
    assert len(backend.records) == 2
    assert len(expected) == 3
    for (actual_values, actual_time), (expected_values, status_count, expected_time) in zip(backend.records[0]['samples'], expected, strict=True):
        np.testing.assert_equal(actual_values, np.concatenate((expected_values, np.full(status_count, np.nan))))
        assert actual_time == pytest.approx(expected_time, abs=1e-10)
    emitter.close()


@pytest.mark.skipif(os.environ.get('FREEMOCAP_LSL_LOOPBACK') != '1',
                   reason='Explicit opt-in for real local LSL sockets')
def test_real_lsl_loopback_preserves_delayed_capture_timestamp_and_provenance():
    import time
    from uuid import uuid4
    pylsl = pytest.importorskip('pylsl')
    name = f'FreeMoCap-test-{uuid4()}'
    clock = LslClockMapping.calibrate(pylsl.local_clock)
    source_ns = time.perf_counter_ns() - 1_000_000_000
    initial = sample_frame(source_ns=source_ns)
    emitter = LslEmitter(LslConfig(stream_name=name), clock=clock)
    numeric_inlet = None
    provenance_inlet = None
    try:
        emitter.emit(initial)
        numeric_info = pylsl.resolve_byprop('name', f'{name}:LANDMARKS_3D', timeout=3.0)
        provenance_info = pylsl.resolve_byprop('name', f'{name}:acquisition', timeout=3.0)
        assert len(numeric_info) == len(provenance_info) == 1
        numeric_inlet = pylsl.StreamInlet(numeric_info[0], processing_flags=0)
        provenance_inlet = pylsl.StreamInlet(provenance_info[0], processing_flags=0)
        numeric_inlet.open_stream(timeout=3.0)
        provenance_inlet.open_stream(timeout=3.0)
        numeric_inlet.pull_chunk(timeout=0.0)
        provenance_inlet.pull_chunk(timeout=0.0)
        # Deliberately publish old, immutable acquisition instants after discovery
        # and connection have incurred additional real delay.
        for index in range(1, 6):
            captured_ns = source_ns + index * 1_000_000
            sample = sample_frame(frame_number=index, source_ns=captured_ns)
            expected_timestamp = clock.to_lsl_seconds(captured_ns)
            emitter.emit(sample)
            numeric, numeric_time = numeric_inlet.pull_sample(timeout=3.0)
            provenance, provenance_time = provenance_inlet.pull_sample(timeout=3.0)
            assert numeric is not None and provenance is not None
            np.testing.assert_equal(numeric, [1.25, np.nan, -3.5, 2.0])
            assert numeric_time == provenance_time == expected_timestamp
            assert pylsl.local_clock() - numeric_time > 0.9
            exact = json.loads(provenance[0])
            assert exact['frame_number'] == index
            assert exact['source_timestamp_ns'] == str(captured_ns)
            assert exact['camera_timestamps_ns'] == {
                'camera-1': str(captured_ns - 1), 'camera-2': str(captured_ns + 1)}
            assert exact['source_frame_gap'] == 0
        # Query complete metadata from the inlet, not the partial resolver result.
        xml = numeric_inlet.info(timeout=2.0).as_xml()
        assert 'head.sample_status' in xml
        assert 'SkellyCam perf_counter_ns' in xml
    finally:
        if numeric_inlet is not None:
            numeric_inlet.close_stream()
        if provenance_inlet is not None:
            provenance_inlet.close_stream()
        emitter.close()


@pytest.mark.skipif(os.environ.get('FREEMOCAP_LSL_LOOPBACK') != '1'
                   or not os.environ.get('FREEMOCAP_LSL_REFERENCE_PARQUET'),
                   reason='Explicit opt-in and reference path required for real LSL replay')
def test_real_lsl_reference_replay_values_timestamps_and_counts(record_property):
    from uuid import uuid4
    import pyarrow.parquet as pq
    pylsl = pytest.importorskip('pylsl')
    path = os.environ['FREEMOCAP_LSL_REFERENCE_PARQUET']
    table = pq.read_table(path, filters=[('channel', '=', 'LANDMARKS_3D')],
        columns=['timestamp_s', 'frame_number', 'source', 'name', 'component', 'value'])
    rows = table.to_pylist()
    assert rows
    source = rows[0]['source']
    frames = {}
    for row in rows:
        if row['source'] == source:
            frames.setdefault(row['frame_number'], []).append(row)
    samples = []
    expectations = []
    for frame_number, frame_rows in sorted(frames.items()):
        names = tuple(dict.fromkeys(row['name'] for row in frame_rows))
        components = tuple(dict.fromkeys(row['component'] for row in frame_rows))
        lookup = {(row['name'], row['component']): row['value'] for row in frame_rows}
        values = np.asarray([lookup[(name, component)] for name in names for component in components], dtype='<f4')
        block = ChannelBlock(ChannelKind.LANDMARKS_3D, components, values.tobytes(), names=names)
        frame = FrameMessage(frame_number=frame_number,
            instances=(ModelInstance(0, 'reference', (block,)),))
        recorded_seconds = frame_rows[0]['timestamp_s']
        samples.append(OutputSample(frame, 'reference-replay', recorded_seconds * 1e9))
        expectations.append((values, recorded_seconds))
    assert len(samples) > 2
    # Declare an explicit replay origin for this relative recorded grid, keeping
    # all fixture instants in the past. This does not claim recovery of unavailable
    # historical perf_counter clock origins from an imported video recording.
    replay_origin = pylsl.local_clock() - expectations[-1][1] - 2.0
    clock = LslClockMapping(0, replay_origin)
    name = f'FreeMoCap-reference-{uuid4()}'
    emitter = LslEmitter(LslConfig(stream_name=name), clock=clock)
    inlet = None
    provenance_inlet = None
    try:
        # First source frame establishes discoverable topology. Verification
        # explicitly starts with the next frame after receiver connection.
        emitter.emit(samples[0])
        infos = pylsl.resolve_byprop('name', f'{name}:LANDMARKS_3D', timeout=3.0)
        provenance_infos = pylsl.resolve_byprop('name', f'{name}:acquisition', timeout=3.0)
        assert len(infos) == len(provenance_infos) == 1
        inlet = pylsl.StreamInlet(infos[0], processing_flags=0)
        provenance_inlet = pylsl.StreamInlet(provenance_infos[0], processing_flags=0)
        inlet.open_stream(timeout=3.0)
        provenance_inlet.open_stream(timeout=3.0)
        inlet.pull_chunk(timeout=0.0)
        provenance_inlet.pull_chunk(timeout=0.0)
        received = 0
        for sample, (expected_values, recorded_seconds) in zip(samples[1:], expectations[1:], strict=True):
            emitter.emit(sample)
            values, timestamp = inlet.pull_sample(timeout=3.0)
            provenance, provenance_timestamp = provenance_inlet.pull_sample(timeout=3.0)
            assert values is not None and provenance is not None
            np.testing.assert_equal(values[:len(expected_values)], expected_values)
            assert len(values) - len(expected_values) == len(sample.frame.instances[0].channels[0].names)
            assert np.isnan(values[len(expected_values):]).all()
            assert timestamp == provenance_timestamp == clock.to_lsl_seconds(sample.source_timestamp_ns)
            assert timestamp == pytest.approx(replay_origin + recorded_seconds, abs=1e-9)
            assert json.loads(provenance[0])['frame_number'] == sample.frame.frame_number
            received += 1
        assert received == len(samples) - 1
        record_property('reference_path', path)
        record_property('reference_frames', len(samples))
        record_property('connected_receiver_samples', received)
        record_property('numeric_values_compared', sum(len(values) for values, _ in expectations[1:]))
    finally:
        if inlet is not None:
            inlet.close_stream()
        if provenance_inlet is not None:
            provenance_inlet.close_stream()
        emitter.close()


@pytest.mark.parametrize('calibrated', [False, True])
def test_default_lsl_accepts_composed_camera_reprojections(calibrated, monkeypatch):
    from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
    from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
    from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction
    from freemocap.core.streaming.message_composer import compose_messages
    from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext
    from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage, CameraNodeOutputMessage

    bundle = build_standard_human_bundle(detector_type='rtmpose')
    names = tuple(bundle.skeleton.segments)
    cameras = ('camera-B', 'camera-A')
    # Deliberately reverse mapping insertion order: row identity is model-owned.
    reprojections = {camera: {names[-1]: np.array([301.25 + index, 402.5]),
                             names[0]: np.array([101.25 + index, 202.5])}
                     for index, camera in enumerate(cameras)}
    reconstruction = SkeletonReconstruction(model_id=bundle.model_id,
        reprojected_segment_origins=reprojections)
    config = RealtimePipelineConfig()
    config.camera_node_config.detector_type = 'rtmpose'
    aggregation = AggregationNodeOutputMessage(frame_number=7, pipeline_config=config,
        camera_group_id='test-group', calibration_applicable=calibrated,
        camera_node_outputs={camera: CameraNodeOutputMessage(camera_id=camera, frame_number=7)
                             for camera in cameras},
        reconstructions={bundle.model_id: reconstruction})
    composition = compose_messages(StreamContext(skeletons=(bundle,), camera_ids=cameras,
        detector_type='rtmpose', pipeline_live=True,
        live_image_sizes={camera: (1280, 720) for camera in cameras}))
    source_ns = 2**56 + 13
    frame = composition.compose_frame_message(FrameContext(7, float(source_ns),
        aggregator_output=aggregation))
    assert frame.diagnostics.length_units == ('millimeters' if calibrated else 'pixels')
    assert tuple(segment.name for segment in frame.models[0].segments) == names
    overlays = [block for block in frame.instances[0].channels
                if block.kind == ChannelKind.OVERLAY_REPROJECTIONS]
    assert len(overlays) == 2 and all(block.names is None for block in overlays)
    sample = OutputSample(frame, 'pipeline-overlay', source_ns,
        tuple((camera, source_ns + index) for index, camera in enumerate(cameras)))
    from freemocap.core.streaming.outputs import lsl as lsl_module
    schema_calls = []
    original_schema = lsl_module.channel_schema
    def counted_schema(**kwargs):
        schema_calls.append(kwargs['identity'])
        return original_schema(**kwargs)
    monkeypatch.setattr(lsl_module, 'channel_schema', counted_schema)
    emitter, backend = emitter_for(sample)
    try:
        emitter.emit(sample)  # Default selects every real composed channel.
        first_schema_count = len(schema_calls)
        records = [record for record in backend.records
                   if record['info'].parameters['channel_format'] == 'float32']
        for record in records:
            metadata = json.loads(record['info'].xml.values['freemocap_metadata'])
            if metadata['kind'] in ('BOXES_2D', 'OVERLAY_2D'):
                assert metadata['channel_length_units'] == 'pixels'
                channels = record['info'].xml.children[0][1].children
                for _, node in channels:
                    if node.values['label'].rsplit('.', 1)[-1] in ('x', 'y', 'x1', 'y1', 'x2', 'y2'):
                        assert node.values['unit'] == 'pixels'
        selected = {json.loads(record['info'].xml.values['freemocap_metadata'])['camera_id']: record
                    for record in records
                    if json.loads(record['info'].xml.values['freemocap_metadata'])['kind']
                    == 'OVERLAY_REPROJECTIONS'}
        assert set(selected) == set(cameras)
        for index, camera in enumerate(cameras):
            record = selected[camera]
            metadata = json.loads(record['info'].xml.values['freemocap_metadata'])
            assert metadata['row_names'] == list(names)
            assert metadata['image_size'] == [1280, 720]
            assert metadata['channel_length_units'] == 'pixels'
            channels = record['info'].xml.children[0][1].children
            assert [node.values['label'] for _, node in channels] == [
                f'{name}.{component}' for name in names for component in ('x', 'y', 'visibility')] + [
                f'{name}.sample_status' for name in names]
            assert [node.values['unit'] for _, node in channels] == [
                'pixels', 'pixels', 'unspecified'] * len(names) + ['status_code'] * len(names)
            values, timestamp = record['samples'][0]
            expected = np.full((len(names), 3), np.nan, dtype='<f4')
            expected[0, :2] = [101.25 + index, 202.5]
            expected[-1, :2] = [301.25 + index, 402.5]
            np.testing.assert_array_equal(np.asarray(values[:expected.size]).reshape(-1, 3), expected)
            assert np.isnan(values[expected.size:]).all()
            assert timestamp == 321.125
        provenance = next(record for record in backend.records
                          if record['info'].parameters['channel_format'] == 'string')
        exact = json.loads(provenance['samples'][0][0][0])
        assert exact['source_timestamp_ns'] == str(source_ns)
        assert exact['camera_timestamps_ns'] == {
            camera: str(source_ns + index) for index, camera in enumerate(cameras)}
        assert sample.camera_timestamps_ns == tuple(
            (camera, source_ns + index) for index, camera in enumerate(cameras))
        equal_frame = replace(frame, frame_number=8,
            models=tuple(replace(model) for model in frame.models),
            convention=replace(frame.convention))
        emitter.emit(replace(sample, frame=equal_frame,
            source_timestamp_ns=source_ns + 50_000_000))
        assert len(schema_calls) == first_schema_count
        changed_model = replace(frame.models[0], segments=tuple(reversed(frame.models[0].segments)))
        with pytest.raises(ValueError, match='schema changed'):
            emitter.emit(replace(sample, frame=replace(frame, frame_number=9, models=(changed_model,)),
                source_timestamp_ns=source_ns + 100_000_000))
        assert all(len(record['samples']) == 2 for record in backend.records)
    finally:
        emitter.close()


def test_lsl_waits_per_outlet_without_backlog_and_releases_partial_preparation():
    sample = sample_frame()
    emitter, backend = emitter_for(sample)
    progress = emitter.prepare(sample)
    assert progress.readiness == 'waiting_for_receiver' and progress.outlets_advertised == 2
    assert all(not record['samples'] for record in backend.records)
    for record in backend.records:
        record['consumers'] = False
    for number in range(1, 5):
        progress = emitter.emit(replace(sample, frame=replace(sample.frame, frame_number=number)))
        assert not progress.sent
    assert all(not record['samples'] for record in backend.records)
    backend.records[0]['consumers'] = True
    progress = emitter.emit(replace(sample, frame=replace(sample.frame, frame_number=5)))
    assert progress.sent and progress.outlets_connected == 1
    assert len(backend.records[0]['samples']) == 1 and not backend.records[1]['samples']
    backend.records[0]['consumers'] = False
    backend.records[1]['consumers'] = True
    progress = emitter.emit(replace(sample, frame=replace(sample.frame, frame_number=6)))
    assert progress.sent and progress.outlets_connected == 1
    provenance = json.loads(backend.records[1]['samples'][0][0][0])
    assert provenance['published_channel_identities'] == []
    assert len(provenance['unsubscribed_channel_identities']) == 1
    emitter.close()
    assert all(record['destroyed'] for record in backend.records)

    class BrokenPreparation(FakeLsl):
        def StreamOutlet(self, info, **kwargs):
            if self.records:
                raise RuntimeError('creation failed')
            return super().StreamOutlet(info, **kwargs)
    broken = BrokenPreparation()
    emitter = LslEmitter(LslConfig(), backend=broken, clock=LslClockMapping(0, 1.0))
    with pytest.raises(RuntimeError, match='creation failed'):
        emitter.prepare(sample)
    assert not emitter._channels and not emitter._provenance
    assert all(record['destroyed'] for record in broken.records)


def evolving_composed_sample(number, generated_support, scale, *, include_angles=True):
    from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
    from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
    from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction
    from freemocap.core.streaming.message_composer import compose_messages
    from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext
    from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage, CameraNodeOutputMessage
    bundle = build_standard_human_bundle(detector_type='rtmpose')
    segment = next(iter(bundle.skeleton.segments))
    joint = next(iter(bundle.skeleton.joints))
    angles = tuple(float(index) + number / 10 for index in range(len(bundle.skeleton.joints[joint].angle_names)))
    reconstruction = SkeletonReconstruction(model_id=bundle.model_id,
        generated_support=generated_support, fitted_scale_mm=scale,
        joint_angles={joint: angles} if include_angles else {},
        segment_origins={segment: np.array([number + .25, 2., 3.])},
        segment_rotations_world={segment: np.array([1., 0., 0., 0.])},
        segment_rotations_local={segment: np.array([1., 0., 0., 0.])},
        reprojected_segment_origins={'camera-A': {segment: np.array([100. + number, 200.])}})
    aggregation = AggregationNodeOutputMessage(frame_number=number,
        pipeline_config=RealtimePipelineConfig(), camera_group_id='fixture',
        calibration_applicable=True,
        camera_node_outputs={camera: CameraNodeOutputMessage(camera_id=camera, frame_number=number)
                             for camera in ('camera-A', 'camera-B')},
        reconstructions={bundle.model_id: reconstruction})
    composition = compose_messages(StreamContext(skeletons=(bundle,), pipeline_live=True,
        camera_ids=('camera-A', 'camera-B'), detector_type='rtmpose',
        live_image_sizes={'camera-A': (1280, 720), 'camera-B': (1280, 720)}))
    ns = 2**56 + 13 + number * 50_000_000
    frame = composition.compose_frame_message(FrameContext(number, float(ns), aggregator_output=aggregation))
    return OutputSample(frame, 'evolving', ns, (('camera-A', ns - 1), ('camera-B', ns + 1)))


def test_composed_generated_support_and_fitted_scale_can_change_without_changing_lsl_layout():
    samples = [evolving_composed_sample(index, generated, scale)
               for index, (generated, scale) in enumerate(((False, 1700.), (True, 1710.), (False, 1720.)))]
    assert any(block.kind == ChannelKind.JOINT_ANGLES for block in samples[0].frame.instances[0].channels)
    emitter, backend = emitter_for(samples[0])
    try:
        for sample in samples:
            emitter.emit(sample)
        numeric = [record for record in backend.records if record['info'].parameters['channel_format'] == 'float32']
        for record in numeric:
            metadata = json.loads(record['info'].xml.values['freemocap_metadata'])
            identity = metadata['identity']
            assert metadata['sample_status_appended'] is True
            assert metadata['sample_status_absent'] == 'NaN: source did not declare row status'
            for sample, (values, timestamp) in zip(samples, record['samples'], strict=True):
                owners = sample.frame.instances if identity[1] == 'instance' else sample.frame.trackers
                owner = next(owner for owner in owners if owner.model_id == identity[3])
                block = next(block for block in owner.channels
                             if block.kind.value == identity[4] and (block.camera_id or '') == identity[5])
                original = np.frombuffer(block.data, dtype='<f4')
                count = len(original) // len(block.columns)
                np.testing.assert_array_equal(values[:len(original)], original)
                expected_status = (np.full(count, np.nan) if block.sample_status is None
                                   else np.frombuffer(block.sample_status, dtype=np.uint8))
                np.testing.assert_array_equal(values[len(original):], expected_status)
                assert timestamp == emitter.clock.to_lsl_seconds(sample.source_timestamp_ns)
        provenance = next(record for record in backend.records if record['info'].parameters['channel_format'] == 'string')
        for sample, (values, _) in zip(samples, provenance['samples'], strict=True):
            exact = json.loads(values[0])
            assert exact['source_timestamp_ns'] == str(sample.source_timestamp_ns)
            expected = sorted([sample.pipeline_id, owner_type, str(owner.instance_id) if owner_type == 'instance' else owner.tracker_id, owner.model_id, block.kind.value, block.camera_id or '']
                              for owner_type, owners in (('instance', sample.frame.instances), ('tracker', sample.frame.trackers))
                              for owner in owners for block in owner.channels if block.sample_status is not None)
            assert exact['status_declared_channel_identities'] == expected
        assert samples[0].frame.instances[0].channels[0].sample_status is None
        assert samples[1].frame.instances[0].channels[0].sample_status is not None
        assert samples[2].frame.instances[0].channels[0].sample_status is None
    finally:
        emitter.close()


def test_status_vocabulary_change_is_rejected_even_after_absent_status_was_cached():
    sample = sample_frame(statuses=None)
    emitter, backend = emitter_for(sample)
    try:
        emitter.emit(sample)
        next_sample = sample_frame(frame_number=1)
        block = next_sample.frame.instances[0].channels[0]
        block = replace(block, status_labels=tuple(reversed(block.status_labels)))
        owner = replace(next_sample.frame.instances[0], channels=(block,))
        with pytest.raises(ValueError, match="status vocabulary.*LANDMARKS_3D.*status_labels"):
            emitter.emit(replace(next_sample, frame=replace(next_sample.frame, instances=(owner,))))
        assert all(len(record['samples']) == 1 for record in backend.records)
    finally:
        emitter.close()


def test_optional_joint_angles_advertise_without_blocking_and_resume_same_outlet():
    import threading
    first = evolving_composed_sample(0, False, 1700., include_angles=False)
    emitter, backend = emitter_for(first)
    entered, release, completed = threading.Event(), threading.Event(), threading.Event()
    original = backend.StreamOutlet
    def delayed(info, **kwargs):
        if info.parameters['name'].endswith(':JOINT_ANGLES'):
            entered.set()
            assert release.wait(3), 'test advertisement was not released'
        result = original(info, **kwargs)
        if info.parameters['name'].endswith(':JOINT_ANGLES'):
            completed.set()
        return result
    backend.StreamOutlet = delayed
    try:
        emitter.emit(first)
        original_ids = [record['info'].parameters['source_id'] for record in backend.records]
        emitter.emit(evolving_composed_sample(1, True, 1710.))
        assert entered.wait(1)
        emitter.emit(evolving_composed_sample(2, False, 1720.))
        emitter.emit(evolving_composed_sample(3, False, 1730., include_angles=False))
        assert all(len(record['samples']) == 4 for record in backend.records)
        provenance = next(record for record in backend.records if record['info'].parameters['channel_format'] == 'string')
        assert any(identity[4] == 'JOINT_ANGLES' for identity in json.loads(provenance['samples'][1][0][0])['preparing_channel_identities'])
        assert any(identity[4] == 'JOINT_ANGLES' for identity in json.loads(provenance['samples'][3][0][0])['absent_channel_identities'])
        release.set()
        assert completed.wait(1)
        # Wait for the descriptor handoff, not a replay of the discovery frame.
        import time
        deadline = time.monotonic() + 1
        while emitter._advertise_results.empty() and time.monotonic() < deadline:
            time.sleep(.001)
        current = evolving_composed_sample(4, True, 1740.)
        emitter.emit(current)
        joint_record = next(record for record in backend.records if record['info'].parameters['name'].endswith(':JOINT_ANGLES'))
        assert len(joint_record['samples']) == 1
        block = next(block for block in current.frame.instances[0].channels if block.kind == ChannelKind.JOINT_ANGLES)
        values = np.frombuffer(block.data, dtype='<f4')
        np.testing.assert_array_equal(joint_record['samples'][0][0][:len(values)], values)
        emitter.emit(evolving_composed_sample(5, False, 1750., include_angles=False))
        assert len(joint_record['samples']) == 1
        emitter.emit(evolving_composed_sample(6, False, 1760.))
        assert len(joint_record['samples']) == 2
        assert [record['info'].parameters['source_id'] for record in backend.records[:-1]] == original_ids
        assert all(len(record['samples']) == 7 for record in backend.records[:-1])
        changed = evolving_composed_sample(7, False, 1770.)
        owner = changed.frame.instances[0]
        blocks = tuple(replace(block, names=tuple(reversed(block.names))) if block.kind == ChannelKind.JOINT_ANGLES else block for block in owner.channels)
        with pytest.raises(ValueError, match='schema changed.*JOINT_ANGLES.*metadata.row_names'):
            emitter.emit(replace(changed, frame=replace(changed.frame, instances=(replace(owner, channels=blocks),))))
        assert len(joint_record['samples']) == 2

    finally:
        release.set()
        emitter.close()
    assert all(record['destroyed'] for record in backend.records)
    assert emitter._advertise_thread is None


def _sample_with_extra_channels(number, extras):
    sample = sample_frame(frame_number=number)
    owner = sample.frame.instances[0]
    additions = tuple(replace(owner.channels[0], kind=ChannelKind.DERIVED_POINTS,
                              names=(f'point-{index}',), camera_id=str(index)) for index in range(extras))
    return replace(sample, frame=replace(sample.frame, instances=(replace(owner, channels=owner.channels + additions),)))


def _wait_for_sync(predicate):
    import time
    deadline = time.monotonic() + 2
    while not predicate():
        assert time.monotonic() < deadline
        time.sleep(.001)


def test_late_advertisement_queue_is_bounded_explicit_and_deduplicated():
    import threading
    emitter, backend = emitter_for(sample_frame())
    entered, release = threading.Event(), threading.Event()
    original = backend.StreamOutlet
    def delayed(info, **kwargs):
        if info.parameters['name'].endswith(':DERIVED_POINTS') and not entered.is_set():
            entered.set()
            assert release.wait(3)
        return original(info, **kwargs)
    backend.StreamOutlet = delayed
    try:
        emitter.emit(_sample_with_extra_channels(0, 0))
        emitter.emit(_sample_with_extra_channels(1, 1))
        assert entered.wait(1)
        emitter.emit(_sample_with_extra_channels(2, 2))
        for number in (3, 4):
            emitter.emit(_sample_with_extra_channels(number, 3))
            coverage = json.loads(backend.records[1]['samples'][-1][0][0])
            assert coverage['advertisement_queue_saturated'] is True
            assert len(coverage['preparing_channel_identities']) == 2
            assert len(coverage['deferred_channel_identities']) == 1
            assert emitter._advertise_requests.qsize() == 1
            assert len(emitter._pending) == 2
        assert len(backend.records[0]['samples']) == 5
        release.set()
        _wait_for_sync(lambda: emitter._advertise_results.qsize() == 2)
        emitter.emit(_sample_with_extra_channels(5, 3))
        _wait_for_sync(lambda: emitter._advertise_results.qsize() == 1)
        emitter.emit(_sample_with_extra_channels(6, 3))
        ids = [record['info'].parameters['source_id'] for record in backend.records]
        assert len(ids) == len(set(ids)) == 5
    finally:
        release.set()
        emitter.close()
    assert all(record['destroyed'] for record in backend.records)


@pytest.mark.parametrize('action', ['stop', 'source_change'])
def test_pending_advertisement_teardown_waits_for_native_call_and_never_adopts_stale_result(action):
    import threading
    emitter, backend = emitter_for(sample_frame())
    entered, release = threading.Event(), threading.Event()
    original = backend.StreamOutlet
    def delayed(info, **kwargs):
        if info.parameters['name'].endswith(':DERIVED_POINTS'):
            entered.set()
            assert release.wait(3)
        return original(info, **kwargs)
    backend.StreamOutlet = delayed
    errors = []
    def operation():
        try:
            if action == 'stop':
                emitter.close()
            else:
                emitter.emit(replace(sample_frame(), pipeline_id='replacement-source'))
        except BaseException as error:
            errors.append(error)
    operation_thread = threading.Thread(target=operation)
    try:
        emitter.emit(_sample_with_extra_channels(0, 0))
        emitter.emit(_sample_with_extra_channels(1, 1))
        assert entered.wait(1)
        operation_thread.start()
        _wait_for_sync(emitter._advertise_stop.is_set)
        assert operation_thread.is_alive()  # Cancellation cannot interrupt native construction.
        release.set()
        operation_thread.join(2)
        assert not operation_thread.is_alive() and not errors
        assert emitter._advertise_thread is None and not emitter._pending
        assert emitter._advertise_results.empty() and emitter._advertise_requests.empty()
        assert all(record['destroyed'] for record in backend.records[:3])
        if action == 'source_change':
            assert len(emitter._channels) == 1
            assert all(identity[0] == 'replacement-source' for identity in emitter._channels)
        else:
            assert not emitter._channels
    finally:
        release.set()
        if operation_thread.ident is not None:
            operation_thread.join(2)
        emitter.close()
    assert all(record['destroyed'] for record in backend.records)


def test_late_advertisement_error_remains_explicit_and_releases_owned_handles():
    emitter, backend = emitter_for(sample_frame())
    original = backend.StreamOutlet
    def failing(info, **kwargs):
        if info.parameters['name'].endswith(':DERIVED_POINTS'):
            raise OSError('native advertisement failed')
        return original(info, **kwargs)
    backend.StreamOutlet = failing
    try:
        emitter.emit(_sample_with_extra_channels(0, 0))
        emitter.emit(_sample_with_extra_channels(1, 1))
        _wait_for_sync(lambda: not emitter._advertise_results.empty())
        with pytest.raises(RuntimeError, match='advertisement failed.*DERIVED_POINTS'):
            emitter.emit(_sample_with_extra_channels(2, 1))
        assert len(backend.records[0]['samples']) == 2
    finally:
        emitter.close()
    assert all(record['destroyed'] for record in backend.records)
