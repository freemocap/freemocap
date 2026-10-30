import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {createServer, type Server} from 'node:http';
import {resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});
let server: Server, url: string;
test.beforeAll(async () => {
    const bundle = await build({entryPoints: ['e2e/fixtures/prepared-renderer-scene.tsx'], bundle: true, write: false,
        format: 'esm', platform: 'browser', jsx: 'automatic', alias: {'@': resolve('src')}});
    server = createServer((request, response) => {
        if (request.url === '/entry.js') {response.setHeader('Content-Type', 'text/javascript'); response.end(bundle.outputFiles[0].text);}
        else {response.setHeader('Content-Type', 'text/html'); response.end('<div id="root" style="width:800px;height:600px"></div><script type="module" src="/entry.js"></script>');}
    });
    await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
    url = `http://127.0.0.1:${(server.address() as any).port}`;
});
test.afterAll(async () => {await new Promise<void>(resolve => {server.close(() => resolve()); server.closeAllConnections();});});
const definition = (count = 2) => ({model_id: 'fixture', scale_reference_name: 'height',
    segments: Array.from({length: count}, (_, i) => ({name: `joint_${i}`, parent: null, primary_axis: 'z', rest_orientation: [1, 0, 0, 0], length_proportion: 0.1, is_fully_specified: true})),
    landmarks: [{name: 'point_a'}, {name: 'point_b'}], connections: [['joint_0', 'joint_1']],
    landmark_groups: [{name: 'points', landmark_names: ['point_a', 'point_b'], color: '#ff0000'}],
    landmark_connections: [{name: 'edge', pairs: [['point_a', 'point_b']], color: '#ff0000'}]});
const frame = (instanceId = 1, offset = 0, count = 2): any => {
    const names = definition(count).segments.map(s => s.name);
    return {modelId: 'fixture', instanceId, fittedScaleMm: 1000,
        segmentOrigins: {names, data: names.flatMap((_, i) => [offset + i * 100, 0, 0])},
        rotations: {boneNames: names, worldQuaternions: names.flatMap(() => [1, 0, 0, 0]), localQuaternions: []},
        segmentLengths: {names, data: names.map(() => 30), fittedScaleMm: 1000},
        landmarks: {names: ['point_a', 'point_b'], data: [offset + 10, 20, 30, offset + 40, 50, 60]},
        mappedKeypoints: null, derived: {centerOfMass: null, xcom: null}};
};
const mesh = (result: any, kind: string) => result.meshes.find((m: any) => m.kind === kind);
const origin = (m: any, slot: number) => m.matrices.slice(slot * 16 + 12, slot * 16 + 15);
const hidden = (m: any, slot: number) => m.matrices.slice(slot * 16, slot * 16 + 16).every((value: number, i: number) => value === (i === 15 ? 1 : 0));

test('occurrence identities, reordered channels, same-count definitions, and visibility update all renderers', async ({page}) => {
    await page.goto(url); await page.waitForFunction(() => (window as any).renderFixture);
    const render = (input: any) => page.evaluate(input => (window as any).renderFixture(input), input);
    const first = frame(1), second = frame(2, 1000);
    let result = await render({definitions: [definition()], frames: [first, second], points: {pointNames: ['left_point', 'face_0000'], interleaved: [1, 2, 3, 4, 5, 6]}});
    expect(origin(mesh(result, 'segment'), 2)).toEqual([1000, 0, 0]);
    expect(origin(mesh(result, 'landmark'), 2)).toEqual([1010, 20, 30]);
    expect(result.connections.positions).toEqual([0, 0, 0, 100, 0, 0, 10, 20, 30, 40, 50, 60, 1000, 0, 0, 1100, 0, 0, 1010, 20, 30, 1040, 50, 60]);
    expect(result.dots).toEqual([4, 5, 6]);
    expect(result.lines[1].slice(36, 39)).toEqual([1000, 0, 0]);
    const firstVersions = mesh(result, 'landmark');
    result = await render({frames: [first, second]});
    expect(mesh(result, 'landmark').colorVersion).toBe(firstVersions.colorVersion);
    expect(mesh(result, 'landmark').matrixVersion).toBeGreaterThan(firstVersions.matrixVersion);
    first.segmentOrigins = {names: ['joint_1', 'joint_0'], data: [100, 0, 0, 0, 0, 0]};
    first.landmarks = {names: ['point_b', 'point_a'], data: [40, 50, 60, 10, 20, 30]};
    result = await render({frames: [second, first]});
    expect(origin(mesh(result, 'segment'), 0)).toEqual([1000, 0, 0]);
    expect(origin(mesh(result, 'segment'), 2)).toEqual([0, 0, 0]);
    expect(origin(mesh(result, 'landmark'), 0)).toEqual([10, 20, 30]);
    expect(result.connections.positions.slice(12, 18)).toEqual([0, 0, 0, 100, 0, 0]);
    const changed = definition(); changed.landmark_groups[0].color = '#00ff00'; changed.landmark_connections[0].color = '#00ff00'; changed.connections = [['joint_1', 'joint_0']];
    result = await render({definitions: [changed], frames: [second, first]});
    expect(mesh(result, 'landmark').colors.slice(0, 3)).toEqual([0, 1, 0]);
    expect(result.connections.positions.slice(0, 6)).toEqual([1100, 0, 0, 1000, 0, 0]);
    expect(result.connections.colors.slice(6, 9)).toEqual([0, 1, 0]);
    first.rotations.worldQuaternions = []; // local-only rotations must hide safely.
    first.rotations.localQuaternions = [1, 0, 0, 0, 1, 0, 0, 0];
    result = await render({frames: [first], points: {pointNames: ['face_0000', 'left_point'], interleaved: [null, null, null, null, null, null]}});
    expect(hidden(mesh(result, 'segment'), 0)).toBe(true);
    expect(hidden(mesh(result, 'segment'), 2)).toBe(true);
    expect(hidden(mesh(result, 'landmark'), 2)).toBe(true);
    expect(mesh(result, 'segment').count).toBe(2);
    expect(mesh(result, 'landmark').count).toBe(2);
    expect(result.dots).toEqual([1e5, 1e5, 1e5]);
    expect(result.lines[1].every((value: number) => value === 0)).toBe(true);
    result = await render({frames: [second, frame(1)]});
    expect(origin(mesh(result, 'landmark'), 2)).toEqual([1010, 20, 30]);
    expect(await page.evaluate(() => (window as any).pickFixture('landmark', 2))).toContainEqual({slot: 2, name: 'point_a'});
});

test('capacity grows beyond former limits while existing meshes and picking remain valid', async ({page}) => {
    await page.goto(url); await page.waitForFunction(() => (window as any).renderFixture);
    const initial = await page.evaluate(input => (window as any).renderFixture(input), {definitions: [definition()], frames: [frame()]});
    const names = Array.from({length: 1030}, (_, i) => `point_${i}`);
    const result = await page.evaluate(input => (window as any).renderFixture(input), {definitions: [definition(300)], frames: [frame(1, 0, 300)],
        points: {pointNames: [...names, ...Array.from({length: 520}, (_, i) => `face_${i}`)], interleaved: [...names.flatMap((_, i) => [i * 100, 0, 0]), ...Array.from({length: 520}, (_, i) => [i, 1, 2]).flat()]}});
    expect(mesh(result, 'segment').uuid).toBe(mesh(initial, 'segment').uuid);
    expect(mesh(result, 'keypoint').capacity).toBeGreaterThanOrEqual(1030);
    expect(mesh(result, 'segment').capacity).toBeGreaterThanOrEqual(300);
    expect(mesh(result, 'segment').count).toBe(300);
    expect(mesh(result, 'keypoint').count).toBe(1030);
    expect(origin(mesh(result, 'segment'), 299)).toEqual([29900, 0, 0]);
    expect(result.dots.length).toBe(520 * 3);
    expect(result.lines[1].length).toBe(300 * 18);
    expect(await page.evaluate(() => (window as any).pickFixture('keypoint', 1029))).toContainEqual({slot: 1029, name: 'point_1029'});
    expect(await page.evaluate(() => (window as any).pickFixture('segment', 299))).toContainEqual({slot: 299, name: 'joint_299'});
    for (let layout = 1; layout <= 3; layout++) {
        const switched = await page.evaluate(input => (window as any).renderFixture(input), {
            points: {pointNames: names.map(name => `${layout}_${name}`), interleaved: names.flatMap((_, i) => [i * 100, 0, 0])},
        });
        expect(mesh(switched, 'keypoint').names.length).toBeLessThanOrEqual(2060);
    }
});

test('axes preserve scalar-first world rotations and face contours clear on layout and validity changes', async ({page}) => {
    await page.goto(url); await page.waitForFunction(() => (window as any).renderFixture);
    const render = (input: any) => page.evaluate(input => (window as any).renderFixture(input), input);
    const rotated = frame();
    rotated.rotations.worldQuaternions = [Math.SQRT1_2, 0, 0, Math.SQRT1_2, 1, 0, 0, 0];
    const contours = ['face.lips_61', 'face.lips_146'];
    let result = await render({definitions: [definition()], frames: [rotated], points: {pointNames: contours, interleaved: [1, 2, 3, 4, 5, 6]}});
    expect(result.lines[0]).toEqual([1, 2, 3, 4, 5, 6]);
    // 90 degrees about +Z maps +X onto +Y, with the triad length 1000 * .1 * .3 = 30 mm.
    expect(result.lines[1][3]).toBeCloseTo(0, 4);
    expect(result.lines[1][4]).toBeCloseTo(30, 4);
    expect(result.lines[1][9]).toBeCloseTo(-30, 4);
    expect(result.lines[1][10]).toBeCloseTo(0, 4);
    result = await render({points: {pointNames: contours, interleaved: [1, 2, 3, null, 5, 6]}});
    expect(result.lines[0]).toEqual(Array(6).fill(1e5));
    result = await render({points: {pointNames: ['face_0000'], interleaved: [10, 20, 30]}});
    expect(result.lines[0]).toEqual([]);
    expect(result.dots).toEqual([10, 20, 30]);
});

test('live retention and playback missing-data behavior feed identical renderer geometry when valid', async ({page}) => {
    await page.goto(url); await page.waitForFunction(() => (window as any).renderFixture);
    const render = (input: any) => page.evaluate(input => (window as any).renderFixture(input), input);
    const valid = {frames: [frame()], points: {pointNames: ['left_point'], interleaved: [1, 2, 3]}};
    const playback = await render({definitions: [definition()], ...valid});
    const live = await render({live: true, ...valid});
    expect(mesh(live, 'segment').matrices).toEqual(mesh(playback, 'segment').matrices);
    expect(live.connections).toEqual(playback.connections);
    const held = await render({frames: [], points: {pointNames: [], interleaved: []}});
    expect(mesh(held, 'segment').matrices).toEqual(mesh(live, 'segment').matrices);
    await page.waitForTimeout(1100);
    const expired = await render({});
    expect(hidden(mesh(expired, 'segment'), 0)).toBe(true);
    const missingPlayback = await render({live: false, frames: [], points: {pointNames: [], interleaved: []}});
    expect(mesh(missingPlayback, 'segment').matrices).toEqual(mesh(expired, 'segment').matrices);
});

test('actual pointer picking preserves model and subject identity through inspection and disappearance', async ({page}) => {
    await page.goto(url); await page.waitForFunction(() => (window as any).renderFixture);
    const render = (input: any) => page.evaluate(input => (window as any).renderFixture(input), input);
    const first = frame(0), second = frame(1, 1000), other = {...frame(0, 2000), modelId: 'other_model'};
    let result = await render({definitions: [definition(), {...definition(), model_id: 'other_model'}], frames: [first, second, other]});
    const target = (modelId: string, instanceId: number) => ({kind: 'landmark', name: 'point_a', modelId, instanceId});
    const slot = (modelId: string, instanceId: number) => mesh(result, 'landmark').targets.find(([, value]: any) => value.name === 'point_a' && value.modelId === modelId && value.instanceId === instanceId)[0];
    const pointer = (index: number, pin = false) => page.evaluate(({index, pin}) => (window as any).pointFixture('landmark', index, pin), {index, pin});
    const inspect = (target: any) => page.evaluate(target => (window as any).inspectFixture(target), target);
    expect((await pointer(slot('fixture', 0))).hovered).toEqual(target('fixture', 0));
    const state = await pointer(slot('fixture', 1), true);
    expect(state.hovered).toEqual(target('fixture', 1));
    expect(state.pinned).toEqual(target('fixture', 1));
    expect((await pointer(slot('other_model', 0))).hovered).toEqual(target('other_model', 0));
    const rows = await inspect(state.pinned);
    expect(rows.find((row: any) => row.label === 'Position (mm)').value.values).toEqual([1010, 20, 30]);
    expect(rows.find((row: any) => row.label === 'Subject instance').value.values).toEqual([1]);
    result = await render({frames: [other, second, first]});
    expect((await pointer(slot('fixture', 1))).hovered).toEqual(target('fixture', 1));
    result = await render({frames: [other, first]});
    expect((await inspect(state.pinned)).find((row: any) => row.label === 'Position (mm)').value.values).toBeNull();
    result = await render({frames: [other, {...second, instanceId: 2}, first]});
    expect((await pointer(slot('fixture', 2))).hovered).toEqual(target('fixture', 2));
    expect((await inspect(state.pinned)).find((row: any) => row.label === 'Position (mm)').value.values).toBeNull();
});


test('direct rendering and inspection consume borrowed tracker channels with declared component order', async ({page}) => {
    await page.goto(url); await page.waitForFunction(() => (window as any).renderFixture);
    const render = (input: any) => page.evaluate(input => (window as any).renderFixture(input), input);
    const points = {pointNames: ['left_point', 'face_0000'], pointSources: [
        {names: ['left_point'], data: [999, 3, 1, 2], stride: 4, coordinateOffsets: [2, 3, 1]},
        {names: ['face_0000'], data: [4, 5, 6]},
    ]};
    let result = await render({definitions: [definition()], frames: [], points});
    expect(origin(mesh(result, 'keypoint'), 0)).toEqual([1, 2, 3]);
    expect(result.dots).toEqual([4, 5, 6]);
    points.pointSources[0].data = [999, 10, 8, 9];
    points.pointSources[1].data = [11, 12, 13];
    result = await render({points});
    expect(origin(mesh(result, 'keypoint'), 0)).toEqual([8, 9, 10]);
    expect(result.dots).toEqual([11, 12, 13]);
    const details = await page.evaluate(() => (window as any).inspectFixture({kind: 'keypoint', name: 'left_point'}));
    expect(details[0].value.values).toEqual([8, 9, 10]);
});
