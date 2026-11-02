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


def test_missing_channel_and_invalid_status_fail_clearly():
    sample = sample_frame()
    emitter, backend = emitter_for(sample)
    emitter.emit(sample)
    missing = replace(sample.frame, frame_number=1, instances=())
    with pytest.raises(ValueError, match='No requested numerical channels'):
        emitter.emit(replace(sample, frame=missing))
    invalid = sample_frame(frame_number=1, statuses=b'\xff')
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
        await wait_until(lambda: all(manager.get(key).frames_emitted == 1 for key in (first.id, second.id)))
        backends[0].records[0]['fail_push'] = True
        source.batch = SourceBatch(samples=(replace(sample,
            frame=replace(sample.frame, frame_number=1),
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
        expected.append((values.copy(), 1000.0 + recorded_seconds))
    assert len(backend.records) == 2
    assert len(expected) == 3
    for (actual_values, actual_time), (expected_values, expected_time) in zip(backend.records[0]['samples'], expected, strict=True):
        np.testing.assert_equal(actual_values, expected_values)
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
            np.testing.assert_equal(values, expected_values)
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
