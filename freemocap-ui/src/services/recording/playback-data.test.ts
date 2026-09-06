import assert from 'node:assert/strict';
import {test} from 'node:test';
import {channelFrame, orderedChannelFrame, sampleAtTime, RecordingComponent, RecordingChannelKind, type PlaybackChannelData} from './playback-data';

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
        frame_numbers: [5], timestamps_s: [0.1], values: [0, 0, 1, 0, 0, 0, 0, 1],
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
        frame_numbers: [5, 6], timestamps_s: [0.1, 0.17], values: [1, 2, 3, null, null, null],
    };
    assert.equal(channelFrame(series, 0.09), null);
    assert.deepEqual(Array.from(channelFrame(series, 0.1)!), [1, 2, 3]);
    assert.ok(Array.from(channelFrame(series, 0.17)!).every(Number.isNaN));
    assert.throws(() => channelFrame({...series, values: [1]}, 0.1), /array length/);
});
