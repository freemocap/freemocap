import assert from 'node:assert/strict';
import {ModelDefinitionSchema} from '../server/transport/message-contract';
import {recordedModelFrame, type PlaybackRun} from './playback-data';
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
