// Bundle with esbuild --platform=node --format=esm; run with node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {Vector3} from 'three';
import asset from './skelly.json';
import {createSkellyMesh, disposeSkellyMesh, prepareSkellyRows, skellyCompatible, updateSkellyPose} from './skelly-binding';
import type {ResolvedModelFrame} from '@/services/server/transport/frame-types';
import type {ModelDefinition} from '@/services/server/transport/message-contract';
import {prepareModels, preparedModelsMatch} from '../prepared-models';

function definition(): ModelDefinition {
    return {model_id: 'fixture', scale_reference_name: 'body_height', segments: asset.parts.map(p => ({name: p.name, parent: p.parent, primary_axis: 'z',
        rest_orientation: p.restOrientation as [number, number, number, number], length_proportion: p.authoredLength, is_fully_specified: true})),
        landmarks: Object.entries(asset.landmarks).map(([name, rest_position]) => ({name, rest_position: rest_position as [number, number, number]})),
        connections: [], landmark_groups: [], landmark_connections: []};
}
function frame(): ResolvedModelFrame {
    const names = asset.parts.map(p => p.name);
    return {modelId: 'fixture', instanceId: 0, fittedScaleMm: 1000,
        segmentOrigins: {names, data: new Float32Array(names.length * 3), stride: 3},
        rotations: {boneNames: names, worldQuaternions: Float32Array.from(names.flatMap(() => [1, 0, 0, 0]))},
        segmentLengths: {names, data: Float32Array.from(asset.parts.map(p => p.authoredLength * 1000)), fittedScaleMm: 1000},
    } as unknown as ResolvedModelFrame;
}

test('artwork compatibility checks geometry, hierarchy and rest rotations, not names alone', () => {
    const model = definition();
    assert.equal(skellyCompatible(asset, model), true);
    model.segments[0].rest_orientation = model.segments[0].rest_orientation.map(v => -v) as [number, number, number, number];
    assert.equal(skellyCompatible(asset, model), true);
    model.landmarks[0].rest_position = [99, 99, 99];
    assert.equal(skellyCompatible(asset, model), false);
    assert.equal(skellyCompatible(asset, undefined), false);
    const changed = definition(); changed.segments[0].parent = 'different';
    assert.equal(skellyCompatible(asset, changed), false);
});

test('rigid GPU binding preserves material triangles and maps vertices through saved world pose', () => {
    const mesh = createSkellyMesh(asset), current = frame(), rows = prepareSkellyRows(asset, current);
    assert.equal(mesh.skeleton.bones.length, 55);
    assert.equal(mesh.geometry.groups.length, 3);
    assert.equal(mesh.geometry.index!.count, asset.parts.reduce((sum, p) => sum + p.indices.length, 0));
    current.segmentOrigins!.data.set([17, 23, 41]);
    const half = Math.sqrt(0.5);
    current.rotations!.worldQuaternions!.set([half, 0, 0, half]);
    current.segmentLengths!.data[0] = asset.parts[0].authoredLength * 1500;
    updateSkellyPose(mesh, asset, rows, current);
    mesh.updateMatrixWorld(true); mesh.skeleton.update();
    const original = new Vector3().fromBufferAttribute(mesh.geometry.attributes.position, 0);
    const actual = mesh.applyBoneTransform(0, original.clone());
    const expected = new Vector3(-original.y * 1500 + 17, original.x * 1500 + 23, original.z * 1500 + 41);
    assert.ok(actual.distanceTo(expected) < 0.001, `${actual.toArray()} vs ${expected.toArray()}`);
    const geometry = mesh.geometry.attributes.position.array;
    current.segmentLengths!.data[0] *= 0.5;
    updateSkellyPose(mesh, asset, rows, current);
    assert.equal(mesh.geometry.attributes.position.array, geometry, 'scale changes must not rebuild vertices');
    current.segmentOrigins!.data[0] = NaN;
    updateSkellyPose(mesh, asset, rows, current);
    assert.equal(mesh.skeleton.bones[0].scale.x, 0);
    assert.ok(mesh.skeleton.bones[1].scale.x > 0);
    disposeSkellyMesh(mesh);
});

test('row permutations and absent rotations never attach to the wrong segment', () => {
    const mesh = createSkellyMesh(asset), current = frame();
    current.segmentOrigins!.names = [...current.segmentOrigins!.names].reverse();
    current.segmentOrigins!.data.set([100, 200, 300]);
    const rows = prepareSkellyRows(asset, current);
    updateSkellyPose(mesh, asset, rows, current);
    assert.deepEqual(mesh.skeleton.bones.at(-1)!.position.toArray(), [100, 200, 300]);
    current.rotations = null;
    updateSkellyPose(mesh, asset, prepareSkellyRows(asset, current), current);
    assert.ok(mesh.skeleton.bones.every(b => b.scale.x === 0));
    disposeSkellyMesh(mesh);
});

test('model replacements rebuild bindings and disposal releases geometry, materials and bone texture', () => {
    const current = frame(), model = definition(), definitions = new Map([['fixture', model]]);
    const prepared = prepareModels([current], definitions);
    assert.equal(preparedModelsMatch(prepared, [current], definitions), true);
    definitions.set('fixture', {...model});
    assert.equal(preparedModelsMatch(prepared, [current], definitions), false);
    const mesh = createSkellyMesh(asset);
    let geometries = 0, materials = 0, textures = 0;
    mesh.geometry.addEventListener('dispose', () => geometries++);
    for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) material.addEventListener('dispose', () => materials++);
    mesh.skeleton.computeBoneTexture();
    mesh.skeleton.boneTexture!.addEventListener('dispose', () => textures++);
    disposeSkellyMesh(mesh);
    assert.deepEqual([geometries, materials, textures], [1, 3, 1]);
});

test('CPU pose update cost and asset topology remain bounded without rebuilding geometry', () => {
    const mesh = createSkellyMesh(asset), current = frame(), rows = prepareSkellyRows(asset, current);
    const geometry = mesh.geometry.attributes.position.array;
    for (let i = 0; i < 100; i++) updateSkellyPose(mesh, asset, rows, current);
    const started = performance.now();
    for (let i = 0; i < 10000; i++) updateSkellyPose(mesh, asset, rows, current);
    const mean = (performance.now() - started) / 10000;
    console.log(`Skelly CPU transform preparation: ${mean.toFixed(4)} ms/frame for ${asset.parts.length} parts; excludes WebGL/GPU`);
    assert.equal(mesh.geometry.attributes.position.array, geometry);
    // The source's 20,011 polygons include 406 quads and three eight-sided faces.
    assert.equal(mesh.geometry.index!.count / 3, 20432);
    assert.equal(mesh.geometry.groups.length, 3);
    disposeSkellyMesh(mesh);
});
