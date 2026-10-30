import assert from 'node:assert/strict';
import {ModelDefinitionSchema} from '../server/transport/message-contract';
import {recordedKeypoints, recordedModelFrame, prepareChannelFrame, prepareRecordedKeypoints, type PlaybackRun} from './playback-data';
import {test} from 'node:test';
import {channelFrame, orderedChannelFrame, sampleAtTime, RecordingComponent, RecordingChannelKind, type PlaybackChannelData} from './playback-data';

test('playback joins dynamic and static channels through declared source identities', () => {
    const model = ModelDefinitionSchema.parse({
        model_id: 'subject', segments: [{
            name: 'root', parent: null, primary_axis: 'z', rest_orientation: [1, 0, 0, 0],
            length_proportion: 1, is_fully_specified: true,
        }, {
            name: 'child', parent: 'root', primary_axis: 'z', rest_orientation: [1, 0, 0, 0],
            length_proportion: 0.5, is_fully_specified: true,
        }], landmarks: [], connections: [],
    });
    const channel = {
        sensor_group: 'cameras', source: 'recorded-instance',
        reference_frame: 'world', names: ['child', 'root'],
    };
    const run: PlaybackRun = {
        run_id: 0, models: [model],
        model_sources: {'recorded-instance': model.model_id},
        channels: [], timelines: [], media: [],
        static_channels: [{
            channel: {...channel, kind: RecordingChannelKind.Lengths, components: {length: 'mm'}},
            values: {child: {length: 50}, root: {length: 100}},
        }],
    };
    const channels: PlaybackChannelData[] = [
        {
            channel: {...channel, kind: RecordingChannelKind.Origins,
                components: {x: 'mm', y: 'mm', z: 'mm'}},
            frame_numbers: [0], timestamps_s: [0], values: new Float64Array([10, 20, 30, 40, 50, 60]),
        },
        {
            channel: {...channel, kind: RecordingChannelKind.WorldRotations,
                components: {w: '1', x: '1', y: '1', z: '1'}},
            frame_numbers: [0], timestamps_s: [0], values: new Float64Array([0, 1, 0, 0, 1, 0, 0, 0]),
        },
    ];
    const frame = recordedModelFrame(run, {
        channels,
    }, model, 'cameras', 0);
    assert.deepEqual(frame.rotations!.boneNames, ['root', 'child']);
    assert.deepEqual(Array.from(frame.segmentOrigins!.data), [40, 50, 60, 10, 20, 30]);
    assert.deepEqual(Array.from(frame.rotations!.worldQuaternions), [1, 0, 0, 0, 0, 1, 0, 0]);
    assert.deepEqual(Array.from(frame.segmentLengths!.data), [100, 50]);
});

test('timestamp selection resolves each native-rate group independently', () => {
    assert.equal(sampleAtTime([0, 1 / 30, 2 / 30], 0.02), 0);
    assert.equal(sampleAtTime([0, 1 / 120, 2 / 120, 3 / 120], 0.02), 2);
    assert.equal(sampleAtTime([0.1, 0.17, 0.25], 0.09), -1);
});

test('renderer layout resolves component and bone order from declarations', () => {
    const series: PlaybackChannelData = {
        channel: {sensor_group: 'mocap', source: 'subject', reference_frame: 'world',
            kind: RecordingChannelKind.WorldRotations, names: ['child', 'root'],
            components: {z: '1', y: '1', x: '1', w: '1'}},
        frame_numbers: [5], timestamps_s: [0.1], values: new Float64Array([0, 0, 1, 0, 0, 0, 0, 1]),
    };
    const layout = {names: ['root', 'child'], components: [RecordingComponent.W, RecordingComponent.X,
        RecordingComponent.Y, RecordingComponent.Z]};
    assert.deepEqual(Array.from(orderedChannelFrame(series, 0.1, layout)!), [1, 0, 0, 0, 0, 1, 0, 0]);
    assert.throws(() => orderedChannelFrame(series, 0.1, {...layout, names: ['root', 'unknown']}), /layout/);
    assert.throws(() => channelFrame({...series, timestamps_s: []}, 0.1), /timestamp array length/);
});

test('channel arrays preserve nonzero frames and missing components', () => {
    const series: PlaybackChannelData = {
        channel: {sensor_group: 'mocap', source: 'subject', reference_frame: 'world',
            kind: RecordingChannelKind.Landmarks, names: ['wrist'], components: {x: 'mm', y: 'mm', z: 'mm'}},
        frame_numbers: [5, 6], timestamps_s: [0.1, 0.17], values: new Float64Array([1, 2, 3, NaN, NaN, NaN]),
    };
    assert.equal(channelFrame(series, 0.09), null);
    assert.deepEqual(Array.from(channelFrame(series, 0.1)!), [1, 2, 3]);
    assert.ok(Array.from(channelFrame(series, 0.17)!).every(Number.isNaN));
    assert.throws(() => channelFrame({...series, values: new Float64Array([1])}, 0.1), /array length/);
});

test('playback preserves distinct tracker, mapped and rigid trajectories across missing frames', () => {
    const model = ModelDefinitionSchema.parse({model_id: 'subject', segments: [],
        landmarks: [{name: 'wrist'}], connections: []});
    const run: PlaybackRun = {run_id: 2, models: [model], model_sources: {'model:subject': 'subject'},
        channels: [], static_channels: [], timelines: [], media: []};
    const channel = (kind: RecordingChannelKind, source: string, name: string, xyz: number[]): PlaybackChannelData => ({
        channel: {sensor_group: 'mocap', source, reference_frame: 'world', kind, names: [name],
            components: {z: 'mm', x: 'mm', y: 'mm'}},
        frame_numbers: [5, 8], timestamps_s: [0.1, 0.2], values: Float64Array.from([...xyz, NaN, NaN, NaN]),
    });
    const channels = [channel(RecordingChannelKind.RawPoints, 'tracker', 'detector_wrist', [3, 1, 2]),
        channel(RecordingChannelKind.RawPoints, 'board', 'corner', [6, 4, 5]),
        channel(RecordingChannelKind.MappedKeypoints, 'model:subject', 'wrist', [30, 10, 20]),
        channel(RecordingChannelKind.Landmarks, 'model:subject', 'wrist', [300, 100, 200])];
    assert.deepEqual(Array.from(recordedKeypoints(channels, 'mocap', 0.1)!.data), [1, 2, 3, 4, 5, 6]);
    const frame = recordedModelFrame(run, {channels}, model, 'mocap', 0.1);
    assert.deepEqual(Array.from(frame.mappedKeypoints!.data), [10, 20, 30]);
    assert.deepEqual(Array.from(frame.landmarks!.data), [100, 200, 300]);
    const absent = recordedModelFrame(run, {channels}, model, 'mocap', 0.2);
    assert.ok(Array.from(absent.mappedKeypoints!.data).every(Number.isNaN));
    assert.ok(Array.from(absent.landmarks!.data).every(Number.isNaN));
    assert.equal(recordedKeypoints(channels, 'other-group', 0.1), null);
    assert.equal(recordedModelFrame(run, {channels}, model, 'other-group', 0.1).mappedKeypoints, null);
});

test('prepared presentation converts once, reuses the selected view and preserves the Float64 source', () => {
    const values = new Float64Array([1.1234567890123, -0, 3, 4, 5, NaN, 7, 8, 9, 10]);
    const source: PlaybackChannelData = {channel: {sensor_group: 'group', source: 'prediction', reference_frame: null,
        kind: RecordingChannelKind.Derived, names: ['point'], components: {e: '1', d: '1', c: '1', b: '1', a: '1'}},
        frame_numbers: [10, 20], timestamps_s: [1, 2], values};
    const originalBytes = new Uint8Array(values.buffer).slice();
    const prepared = prepareChannelFrame(source, {names: ['point'], components: ['a', 'b', 'c', 'd', 'e']});
    assert.equal(prepared.read(0.9), null);
    const first = prepared.read(1)!;
    assert.equal(prepared.read(1.5), first);
    assert.deepEqual(Array.from(first), [5, 4, 3, -0, Math.fround(1.1234567890123)]);
    const second = prepared.read(2)!;
    assert.equal(first.buffer, second.buffer, 'views share a prepared dense presentation tensor');
    assert.equal(second.length, 5);
    assert.equal(prepared.read(0.5), null);
    assert.deepEqual(Array.from(prepared.read(1)!), Array.from(first));
    assert.deepEqual(new Uint8Array(values.buffer), originalBytes);
    assert.notEqual(first.buffer, values.buffer);
});

test('prepared raw sources preserve late starts and independent clocks across reverse seeking', () => {
    const source = (name: string, times: number[], values: number[]): PlaybackChannelData => ({
        channel: {sensor_group: 'group', source: name, reference_frame: 'world', kind: RecordingChannelKind.RawPoints,
            names: [name], components: {z: 'mm', x: 'mm', y: 'mm'}},
        frame_numbers: times.map((_, index) => index + 10), timestamps_s: times, values: new Float64Array(values),
    });
    const channels = [source('early', [1, 2], [3, 1, 2, 6, 4, 5]), source('late', [1.5, 1.75], [30, 10, 20, 60, 40, 50])];
    const read = prepareRecordedKeypoints(channels, 'group');
    assert.equal(read(0.5), null);
    assert.deepEqual(read(1)!.names, ['early']);
    assert.deepEqual(Array.from(read(1)!.data), [1, 2, 3]);
    const both = read(1.6)!;
    assert.deepEqual(both.names, ['early', 'late']);
    assert.deepEqual(Array.from(both.data), [1, 2, 3, 10, 20, 30]);
    const mergedBuffer = both.data.buffer;
    assert.equal(read(1.8)!.data.buffer, mergedBuffer);
    assert.deepEqual(Array.from(read(1.8)!.data), [1, 2, 3, 40, 50, 60]);
    assert.deepEqual(read(1.2)!.names, ['early']);
    assert.deepEqual(Array.from(read(2)!.data), [4, 5, 6, 40, 50, 60]);
    assert.equal(read(0.5), null);
});
