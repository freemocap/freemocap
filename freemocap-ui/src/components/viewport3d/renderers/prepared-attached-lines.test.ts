// Bundle with esbuild --platform=node --format=cjs; run Node's test runner.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {ModelDefinitionSchema} from '@/services/server/transport/message-contract';
import type {ResolvedModelFrame} from '@/services/server/transport/frame-types';
import {prepareModels, preparedModelsMatch} from './prepared-models';
import {prepareAttachedLines, writeAttachedLines, HIDDEN_LINE_COORDINATE} from './prepared-attached-lines';
import {prepareBones, writeBoneMatrices} from './prepared-bones';

const definition = ModelDefinitionSchema.parse({model_id: 'fixture', segments: [{name: 'body', parent: null,
    primary_axis: 'y', rest_orientation: [.5, .5, .5, .5], length_proportion: .1, is_fully_specified: true}], landmarks: [], connections: [],
    presentation: {attached_lines: [{segment: 'body', authored_length: .1, positions: [.1, 0, 0, 0, .1, 0]}],
        excluded_origin_edges: [], excluded_bones: ['body']}});
function frame(): ResolvedModelFrame {
    return {modelId: 'fixture', instanceId: 2, fittedScaleMm: 2000,
        segmentOrigins: {names: ['other', 'body'], stride: 4, coordinateOffsets: [2, 0, 3], data: Float32Array.from([0, 0, 0, 0, 20, 99, 10, 30])},
        rotations: {boneNames: ['body'], worldQuaternions: Float32Array.from([Math.SQRT1_2, 0, 0, Math.SQRT1_2]), localQuaternions: new Float32Array()},
        segmentLengths: {names: ['body'], data: Float32Array.from([100]), fittedScaleMm: 2000},
        landmarks: null, mappedKeypoints: null, derived: {centerOfMass: null, xcom: null}};
}
const definitions = new Map([['fixture', definition]]);

test('local contours use permuted rows/coordinates, measured scale and world rotation exactly once', () => {
    const f = frame(), models = prepareModels([f], definitions), batch = prepareAttachedLines(models, 1)[0];
    const out = new Float32Array(12), scratch = new Float64Array(9), source = f.segmentOrigins!.data.slice();
    assert.equal(writeAttachedLines(batch, f, out, scratch), true);
    [10, 120, 30, -90, 20, 30].forEach((v, i) => assert.ok(Math.abs(out[6 + i] - v) < 1e-4));
    assert.deepEqual(out.slice(0, 6), new Float32Array(6));
    assert.deepEqual(f.segmentOrigins!.data, source);
    const local = batch.positions;
    for (let i = 0; i < 500; i++) writeAttachedLines(batch, f, out, scratch);
    assert.equal(batch.positions, local);
    assert.equal(preparedModelsMatch(models, [frame()], definitions), true);
    assert.equal(preparedModelsMatch(models, [f], new Map([['fixture', {...definition}]])), false);
});

test('missing or invalid pose clears prior geometry, never substitutes an arbitrary size', () => {
    for (const kind of ['origin', 'rotation', 'localOnly', 'zeroQuaternion', 'length', 'noScale'] as const) {
        const f = frame(), batch = prepareAttachedLines(prepareModels([f], definitions), 0)[0];
        if (kind === 'origin') f.segmentOrigins!.data.fill(NaN);
        if (kind === 'rotation') f.rotations = null;
        if (kind === 'localOnly') f.rotations!.worldQuaternions = new Float32Array();
        if (kind === 'zeroQuaternion') f.rotations!.worldQuaternions.fill(0);
        if (kind === 'length') f.segmentLengths!.data.fill(NaN);
        if (kind === 'noScale') {f.segmentLengths = null; f.fittedScaleMm = null;}
        const out = new Float32Array(6).fill(123);
        assert.equal(writeAttachedLines(batch, f, out, new Float64Array(9)), false, kind);
        assert.deepEqual(out, new Float32Array(6).fill(HIDDEN_LINE_COORDINATE));
    }
});

test('legacy definitions have no contours and excluded bones retain stable picking slots', () => {
    const f = frame(), models = prepareModels([f], definitions);
    const out = new Float32Array(16);
    writeBoneMatrices(prepareBones(models[0], 0), f, out, new Float64Array(9));
    assert.deepEqual([...out], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]);
    const legacy = {...definition, presentation: undefined};
    assert.deepEqual(prepareAttachedLines(prepareModels([f], new Map([['fixture', legacy]])), 0), []);
    writeBoneMatrices(prepareBones(prepareModels([f], new Map([['fixture', legacy]]))[0], 0), f, out, new Float64Array(9));
    assert.notEqual(out[12], 0);
});

test('instances have independent prepared ranges and a measured model scale can size an absent length channel', () => {
    const first = frame(), second = frame();
    second.instanceId = 3;
    second.segmentLengths = null;
    const batches = prepareAttachedLines(prepareModels([first, second], definitions), 0);
    assert.deepEqual(batches.map(batch => batch.baseEdge), [0, 1]);
    const out = new Float32Array(12), rotation = new Float64Array(9);
    writeAttachedLines(batches[0], first, out, rotation);
    writeAttachedLines(batches[1], second, out, rotation);
    assert.ok(Math.abs(out[1] - 120) < 1e-4);
    assert.ok(Math.abs(out[7] - 220) < 1e-4);
    // A missing row in a PRESENT channel must hide, even with a measured model scale.
    first.segmentLengths = {...first.segmentLengths!, names: ['other']};
    const missing = prepareAttachedLines(prepareModels([first], definitions), 0)[0];
    assert.equal(writeAttachedLines(missing, first, out, rotation), false);
});
