import assert from 'node:assert/strict';
import {test} from 'node:test';
import {Matrix4, Vector3} from 'three';
import {fittedSkeletonFrames, fittedWorldPoint} from './fitted-skeleton';
import {FittedSkeletonSchema} from './fitted-skeleton-types';
import {type PlaybackRun, type PlaybackChannelData} from './playback-data';
import {FittedSkeletonInstances} from '@/components/viewport3d/renderers/FittedSkeletonInstances';
import {getPickingEntries} from '@/components/viewport3d/renderers/PickingRegistry';

const source = 'skeleton_fit:cameras:standard_human';
const definition = FittedSkeletonSchema.parse({model_id: 'standard_human', sensor_group: 'cameras',
    converged: true, report: 'fixture', geometry: {names: ['spine'], parents: [], attachments: [],
        display_names: [['tip']], display: [[[10, 20, 100]]], references: [100]}});
const run: PlaybackRun = {run_id: 0, models: [], model_sources: {}, static_channels: [], channels: [],
    timelines: [], media: [], fitted_skeletons: {[source]: definition}};
function channels(): PlaybackChannelData[] {
    const base = {source, sensor_group: 'cameras', reference_frame: 'world', names: ['spine']};
    const q = Math.SQRT1_2;
    const series: {kind: string; components: Record<string, string>; values: number[]}[] = [
        {kind: 'SEGMENT_ORIGINS', components: {z: 'mm', x: 'mm', y: 'mm'}, values: [30, 10, 20, 60, 40, 50]},
        {kind: 'ROTATIONS_WORLD', components: {x: '1', w: '1', z: '1', y: '1'}, values: [0, q, q, 0, 0, 1, 0, 0]},
        {kind: 'SEGMENT_LENGTHS', components: {length: 'mm'}, values: [50, 200]},
    ];
    return series.map(item => ({channel: {...base, kind: item.kind, components: item.components},
        frame_numbers: [10, 11], timestamps_s: [1, 2], values: Float64Array.from(item.values)}));
}
function close(actual: number[], expected: number[]) {
    actual.forEach((value, i) => assert.ok(Math.abs(value - expected[i]) < 1e-4, `${actual} != ${expected}`));
}

test('a wholly absent frame stays blank and re-entry still renders', () => {
    const data = channels();
    for (const item of data) item.values.fill(NaN, 0, item.values.length / 2);
    assert.deepEqual(fittedSkeletonFrames(run, data, 'cameras', 1), []);
    assert.equal(fittedSkeletonFrames(run, data, 'cameras', 2).length, 1);
});

test('saved transforms preserve component order, axial-only deformation, and backward seeking', () => {
    const data = channels();
    assert.deepEqual(fittedSkeletonFrames(run, data, 'cameras', 0), []);
    const first = fittedSkeletonFrames(run, data, 'cameras', 1.5)[0];
    close(fittedWorldPoint(definition, first, 0, [10, 20, 100]).toArray(), [-10, 30, 80]);
    const last = fittedSkeletonFrames(run, data, 'cameras', 2)[0];
    close(fittedWorldPoint(definition, last, 0, [10, 20, 100]).toArray(), [50, 70, 260]);
    assert.deepEqual(fittedSkeletonFrames(run, data, 'cameras', 1)[0], first);
    assert.deepEqual(fittedSkeletonFrames({...run, fitted_skeletons: undefined}, data, 'cameras', 1), []);
    assert.deepEqual(fittedSkeletonFrames(run, data, 'other-camera-group', 1), []);
});

test('inconsistent channels are omitted without blocking playback or later valid frames', () => {
    const data = channels(); data[1].frame_numbers[0] = 9;
    assert.deepEqual(fittedSkeletonFrames(run, data, 'cameras', 1), []);
    assert.equal(fittedSkeletonFrames(run, data, 'cameras', 2).length, 1);
    const reference = channels(); reference[1].channel.reference_frame = 'other';
    assert.deepEqual(fittedSkeletonFrames(run, reference, 'cameras', 1), []);
    assert.deepEqual(fittedSkeletonFrames(run, channels().slice(0, 2), 'cameras', 1), []);
});

test('bad positions, quaternions and axial lengths hide samples and recover on seek', () => {
    for (const [channel, value] of [[0, NaN], [1, 0], [2, 0], [2, -1], [2, Infinity]]) {
        const bad = channels();
        if (channel === 1) bad[1].values.fill(0, 0, 4);
        else bad[channel].values[0] = value;
        const frame = fittedSkeletonFrames(run, bad, 'cameras', 1)[0];
        assert.deepEqual([...frame.validSegments], [0]);
        const mesh = new FittedSkeletonInstances({source, definition});
        try {
            mesh.update(frame, true, true);
            assert.equal(mesh.sticks.count + mesh.origins.count + mesh.axes.count, 0);
            assert.equal(getPickingEntries().get(mesh.origins)!.instanceIdToName.size, 0);
            mesh.update(fittedSkeletonFrames(run, bad, 'cameras', 2)[0], true, true);
            assert.equal(mesh.sticks.count, 1);
            assert.equal(mesh.origins.count, 1);
            assert.equal(mesh.axes.count, 3);
            mesh.update(frame, true, true);
            assert.equal(mesh.sticks.count + mesh.origins.count + mesh.axes.count, 0);
        } finally {mesh.dispose();}
    }
});

test('a corrupt segment does not hide its valid neighbor or mislabel picking', () => {
    const two = FittedSkeletonSchema.parse({...definition, geometry: {...definition.geometry,
        names: ['bad', 'good'], display: [[[0, 0, 100]], [[0, 0, 100]]],
        display_names: [['bad_tip'], ['good_tip']], references: [100, 100]}});
    const mesh = new FittedSkeletonInstances({source, definition: two});
    try {
        mesh.update({source, origins: Float32Array.from([NaN, 0, 0, 10, 20, 30]),
            quaternions: Float32Array.from([0, 0, 0, 0, 1, 0, 0, 0]),
            lengths: Float32Array.from([0, 100]), validSegments: Uint8Array.from([0, 1])}, true, true);
        assert.equal(mesh.sticks.count, 1); assert.equal(mesh.axes.count, 3);
        assert.equal(getPickingEntries().get(mesh.origins)!.instanceIdToName.get(0), 'Fitted good origin');
        assert.equal(getPickingEntries().get(mesh.sticks)!.instanceIdToName.get(0), 'Fitted good → good_tip');
        const matrix = new Matrix4(); mesh.origins.getMatrixAt(0, matrix);
        close(new Vector3().setFromMatrixPosition(matrix).toArray(), [10, 20, 30]);
    } finally {mesh.dispose();}
});

test('visible sticks use saved endpoints; axes toggle independently and hidden geometry is not pickable', () => {
    const before = getPickingEntries().size;
    const mesh = new FittedSkeletonInstances({source, definition});
    const frame = fittedSkeletonFrames(run, channels(), 'cameras', 1)[0];
    try {
        mesh.update(frame, true, false);
        assert.equal(mesh.sticks.count, 1); assert.equal(mesh.axes.count, 0);
        const matrix = new Matrix4(); mesh.sticks.getMatrixAt(0, matrix);
        close(new Vector3(0, -0.5, 0).applyMatrix4(matrix).toArray(), [10, 20, 30]);
        close(new Vector3(0, 0.5, 0).applyMatrix4(matrix).toArray(), [-10, 30, 80]);
        assert.match(getPickingEntries().get(mesh.sticks)!.instanceIdToName.get(0)!, /spine.*tip/);
        mesh.update(frame, false, true);
        assert.equal(mesh.sticks.count, 0); assert.equal(mesh.axes.count, 3); assert.equal(mesh.origins.count, 1);
        mesh.axes.getMatrixAt(0, matrix);
        const direction = new Vector3(0, 1, 0).transformDirection(matrix);
        close(direction.toArray(), [0, 1, 0]); // saved rotation turns local X into world Y
        mesh.update(frame, false, false);
        assert.equal(mesh.origins.count, 0); assert.equal(mesh.sticks.count, 0); assert.equal(mesh.axes.count, 0);
        mesh.update(undefined, true, true);
        assert.equal(mesh.origins.count, 0);
    } finally {mesh.dispose();}
    assert.equal(getPickingEntries().size, before);
});
