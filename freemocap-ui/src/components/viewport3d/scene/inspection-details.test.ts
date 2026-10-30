// Bundle with esbuild (platform=node, format=cjs, @=src), then run node --test.
// Reference acceptance additionally uses FREEMOCAP_PLAYBACK_PARQUET and
// FREEMOCAP_PLAYBACK_MANIFEST pointing at the prepared reference and its manifest.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {computeInspectionDetails} from './inspection-details';
import {sameInspectionTarget, type InspectionTarget} from '../helpers/viewport3d-types';
import {ModelDefinitionSchema} from '@/services/server/transport/message-contract';
import type {ResolvedModelFrame} from '@/services/server/transport/frame-types';

const source = {getLatestKeypoints: () => ({pointNames: ['shared'], interleaved: new Float32Array([7, 8, 9])})};
const definition = (modelId: string) => ModelDefinitionSchema.parse({model_id: modelId,
    segments: [{name: 'shared', parent: null, rest_orientation: [1, 0, 0, 0], primary_axis: 'z', length_proportion: .5, is_fully_specified: true}],
    landmarks: [{name: 'shared', rest_position: [1, 2, 3]}], connections: []});
const definitions = new Map(['first_model', 'second_model'].map(id => [id, definition(id)]));
function frame(modelId: string, instanceId: number, offset: number): ResolvedModelFrame {
    const points = {names: ['shared'], data: new Float32Array([.9, offset + 3, offset + 1, offset + 2, -1]), stride: 5, coordinateOffsets: [2, 3, 1] as const};
    return {modelId, instanceId, fittedScaleMm: offset + 100, segmentOrigins: points, landmarks: points, mappedKeypoints: points,
        segmentLengths: {names: ['shared'], data: new Float32Array([offset + 10]), fittedScaleMm: offset + 100},
        rotations: {boneNames: ['shared'], worldQuaternions: new Float32Array([1, 0, 0, 0]), localQuaternions: new Float32Array([0, 1, 0, 0])},
        derived: {centerOfMass: null, xcom: null}};
}
const values = (target: InspectionTarget, frames: ResolvedModelFrame[], label: string, modelDefinitions = definitions) => {
    const row = computeInspectionDetails(target, source, frames, modelDefinitions).find(row => row.label === label)!;
    assert.equal(row.value.kind, 'numbers'); return row.value.values;
};

test('model and subject identities select exact strided coordinates independently of frame order', () => {
    const frames = [frame('first_model', 0, 0), frame('first_model', 1, 100), frame('second_model', 0, 200)];
    for (const order of [frames, frames.toReversed()]) for (const kind of ['segment', 'landmark', 'mapped keypoint'] as const) {
        for (const [modelId, instanceId, offset] of [['first_model', 0, 0], ['first_model', 1, 100], ['second_model', 0, 200]] as const) {
            const target = {kind, name: 'shared', modelId, instanceId};
            assert.deepEqual(values(target, order, kind === 'segment' ? 'Origin (mm)' : 'Position (mm)'), [offset + 1, offset + 2, offset + 3]);
            assert.deepEqual(values(target, order, 'Subject instance'), [instanceId]);
            if (kind === 'segment') assert.deepEqual(values(target, order, 'Length (mm)'), [offset + 10]);
        }
    }
});

test('delayed selection never borrows another occurrence when its selected instance disappears', () => {
    const target = structuredClone({kind: 'landmark', name: 'shared', modelId: 'first_model', instanceId: 0} as const);
    const remaining = [frame('first_model', 1, 100), frame('second_model', 0, 200)];
    assert.equal(values(target, remaining, 'Position (mm)'), null);
    assert.deepEqual(values(target, remaining, 'Subject instance'), [0]);
    assert.deepEqual(values(target, [frame('first_model', 0, 300), ...remaining], 'Position (mm)'), [301, 302, 303]);
});

test('definition replacement refreshes authored values without changing selected identity', () => {
    const target = {kind: 'landmark', name: 'shared', modelId: 'first_model', instanceId: 0} as const;
    const changed = definition('first_model'); changed.landmarks[0].rest_position = [4, 5, 6];
    assert.deepEqual(values(target, [], 'Rest position (model units)', new Map([['first_model', changed]])), [4, 5, 6]);
});

test('hover equality distinguishes identical names across models and instances, including instance zero', () => {
    const first = {kind: 'segment', name: 'shared', modelId: 'first_model', instanceId: 0} as const;
    assert.ok(sameInspectionTarget(first, {...first}));
    assert.ok(!sameInspectionTarget(first, {...first, instanceId: 1}));
    assert.ok(!sameInspectionTarget(first, {...first, modelId: 'second_model'}));
    assert.ok(!sameInspectionTarget(first, null));
    assert.ok(sameInspectionTarget({kind: 'keypoint', name: 'shared'}, {kind: 'keypoint', name: 'shared'}));
    assert.deepEqual(values({kind: 'keypoint', name: 'shared'}, [], 'Position (mm)'), [7, 8, 9]);
});

test('reference recording inspection resolves every model occurrence and coordinate', {
    skip: !process.env.FREEMOCAP_PLAYBACK_PARQUET || !process.env.FREEMOCAP_PLAYBACK_MANIFEST,
}, async () => {
    const {readFileSync} = await import('node:fs');
    const {PlaybackManifestSchema, prepareRecordedModelFrame} = await import('@/services/recording/playback-data');
    const {decodePlaybackParquet} = await import('@/services/recording/playback-parquet');
    const bytes = readFileSync(process.env.FREEMOCAP_PLAYBACK_PARQUET!);
    const manifest = PlaybackManifestSchema.parse(JSON.parse(readFileSync(process.env.FREEMOCAP_PLAYBACK_MANIFEST!, 'utf8')));
    const decoded = await decodePlaybackParquet(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), manifest);
    const run = manifest.runs.find(run => run.run_id === manifest.selected_run_id)!;
    const group = run.channels.find(channel => channel.kind === 'LANDMARKS_3D')!.sensor_group;
    const readers = run.models.map(model => prepareRecordedModelFrame(run, {channels: decoded[run.run_id]}, model, group));
    const definitions = new Map(run.models.map(model => [model.model_id, model]));
    const times = decoded[run.run_id].find(series => series.channel.kind === 'LANDMARKS_3D')!.timestamps_s;
    assert.equal(times.length, 222);
    let checked = 0;
    for (const timestamp of times) {
        const frames = readers.map(read => read(timestamp));
        for (const frame of frames) for (const [kind, field, label] of [
            ['segment', 'segmentOrigins', 'Origin (mm)'], ['landmark', 'landmarks', 'Position (mm)'],
            ['mapped keypoint', 'mappedKeypoints', 'Position (mm)'],
        ] as const) {
            const points = frame[field]; if (!points) continue;
            points.names.forEach((name, index) => {
                const target = {kind, name, modelId: frame.modelId, instanceId: frame.instanceId};
                const result = computeInspectionDetails(target, source, frames.toReversed(), definitions);
                const position = result.find(row => row.label === label)!.value;
                assert.equal(position.kind, 'numbers');
                assert.deepEqual(position.values, Array.from(points.data.subarray(index * 3, index * 3 + 3)));
                checked++;
            });
        }
    }
    assert.ok(checked > 50000);
});
