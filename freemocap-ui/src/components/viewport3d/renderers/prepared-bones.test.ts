// Bundle with esbuild --platform=node --format=cjs, then node --test the ignored bundle.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {ModelDefinitionSchema, type PrimaryAxis} from '@/services/server/transport/message-contract';
import type {ResolvedModelFrame} from '@/services/server/transport/frame-types';
import {computeBoneMatrix, REGION_CROSS_SECTION, classifyRegion} from './RigidBodyBoneInstances';
import {prepareModels, preparedModelsMatch} from './prepared-models';
import {prepareBones, writeBoneMatrices} from './prepared-bones';

const axes: PrimaryAxis[] = ['x', '-x', 'y', '-y', 'z', '-z', [1, 2, -3], [-0.3, 0.7, 0.2]];
const definition = ModelDefinitionSchema.parse({model_id: 'fixture', segments: axes.map((primary_axis, i) => ({
    name: `left_bone_${i}`, parent: null, primary_axis, rest_orientation: [0.5, 0.5, 0.5, 0.5], length_proportion: 0.1 + i / 10, is_fully_specified: true,
})), landmarks: [], connections: []});
const names = definition.segments.map(segment => segment.name);
function frame(): ResolvedModelFrame {
    return {modelId: 'fixture', instanceId: 1, fittedScaleMm: 1000,
        segmentOrigins: {names, data: Float32Array.from(names.flatMap((_, i) => [i * 10, -i, 100 + i]))},
        rotations: {boneNames: names, worldQuaternions: Float32Array.from(names.flatMap((_, i) => [Math.cos(i / 2), 0, Math.sin(i / 2), 0])), localQuaternions: new Float32Array()},
        segmentLengths: {names, data: Float32Array.from(names.map((_, i) => i ? 20 + i : NaN)), fittedScaleMm: 1000},
        landmarks: null, mappedKeypoints: null, derived: {centerOfMass: null, xcom: null}};
}
const definitions = new Map([[definition.model_id, definition]]);

test('prepared transforms match the existing matrix implementation for signed/vector axes and rest semantics', () => {
    const f = frame(), models = prepareModels([f], definitions), bones = prepareBones(models[0], 0);
    const result = new Float32Array(names.length * 16);
    writeBoneMatrices(bones, f, result, new Float64Array(9));
    for (let row = 0; row < names.length; row++) {
        const segment = definition.segments[row];
        const expected = computeBoneMatrix(Array.from(f.segmentOrigins!.data.slice(row * 3, row * 3 + 3)) as [number, number, number],
            Array.from(f.rotations!.worldQuaternions.slice(row * 4, row * 4 + 4)) as [number, number, number, number],
            segment.rest_orientation, segment.primary_axis, row ? 20 + row : 100, REGION_CROSS_SECTION[classifyRegion(segment.name)])!;
        assert.deepEqual(result.slice(row * 16, row * 16 + 16), Float32Array.from(expected));
    }
});

test('named channel permutations resolve independently and same-count definitions invalidate prepared data', () => {
    const f = frame(), original = prepareModels([f], definitions);
    const expected = new Float32Array(names.length * 16);
    writeBoneMatrices(prepareBones(original[0], 0), f, expected, new Float64Array(9));
    const reversed = {...f, segmentOrigins: {names: [...names].reverse(), data: Float32Array.from([...names].reverse().flatMap((_, i) => Array.from(f.segmentOrigins!.data.slice((names.length - 1 - i) * 3, (names.length - i) * 3))))}};
    assert.equal(preparedModelsMatch(original, [reversed], definitions), false);
    const actual = new Float32Array(expected.length);
    writeBoneMatrices(prepareBones(prepareModels([reversed], definitions)[0], 0), reversed, actual, new Float64Array(9));
    assert.deepEqual(actual, expected);
    assert.equal(preparedModelsMatch(original, [f], new Map([['fixture', {...definition, connections: [['left_bone_0', 'left_bone_1']]}]])), false);
    assert.equal(preparedModelsMatch(original, [{...f, instanceId: 2}], definitions), false);
    assert.equal(preparedModelsMatch(original, [frame()], definitions), true);
});

test('missing/nonfinite origins and local-only rotations produce zero-scaled finite matrices', () => {
    for (const missing of ['origins', 'rotations', 'world', 'infinity'] as const) {
        const f = frame();
        if (missing === 'origins') f.segmentOrigins = null;
        if (missing === 'rotations') f.rotations = null;
        if (missing === 'world') f.rotations!.worldQuaternions = new Float32Array();
        if (missing === 'infinity') f.segmentOrigins!.data.fill(Infinity);
        const result = new Float32Array(names.length * 16).fill(123);
        writeBoneMatrices(prepareBones(prepareModels([f], definitions)[0], 0), f, result, new Float64Array(9));
        for (let row = 0; row < names.length; row++) assert.deepEqual(Array.from(result.slice(row * 16, row * 16 + 16)), [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]);
    }
});
