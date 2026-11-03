import assert from 'node:assert/strict';
import {test} from 'node:test';
import {ProcessingPlanSchema, type TaskOperation} from '@/services/server/transport/message-contract';
import type {LaunchedRun} from './graph-model';
import {sectionGraph, type SectionSettings} from './section-graph';
import {portOffset, sectionLayout} from './section-layout';
// Plans from the production recipes; regenerate with tools/make-processing-plan-fixtures.py.
import full from './fixtures/plan-full.json';
import fromFiltering from './fixtures/plan-from-filtering.json';
import toTriangulation from './fixtures/plan-to-triangulation.json';

const settings: SectionSettings = {
    recordingName: 'freemocap_sample_data', calibrationFile: 'freemocap_sample_data_camera_calibration.toml',
    detector: 'RTMW', detectorRows: [{label: 'Model', value: 'Default'}], charuco: true, alignment: 'Automatic', customTransform: false,
    triangulation: {outlierRejection: true, minimumCameras: 2, maximumDropped: 1, targetError: 0.02},
    filter: {enabled: true, cutoff: 6, order: 4},
    blender: {executableFound: true, exportAfter: false, openWhenDone: false, formats: []},
    exports: {formats: [], exportAfter: false, tallCsv: false, channels: ['LANDMARKS_3D']},
};
const plans = {full: ProcessingPlanSchema.parse(full.plan), fromFiltering: ProcessingPlanSchema.parse(fromFiltering.plan),
    toTriangulation: ProcessingPlanSchema.parse(toTriangulation.plan)};
const operation = (id: string, changes: Partial<TaskOperation> = {}): TaskOperation => ({operation_id: id, label: id, status: 'waiting',
    progress_fraction: null, detail: '', completed: null, total: null, unit: null, elapsed_seconds: null, seconds_per_motion_frame: null, ...changes});

test('the graph is the panel sections in order, every plan node in exactly one of them', () => {
    for (const plan of Object.values(plans)) {
        const graph = sectionGraph(settings, plan, null);
        assert.deepEqual(graph.nodes.map(node => node.title), ['Recording', 'SkellyTracker', 'SkellyForge', 'Blender add-on', 'Exports']);
        assert.deepEqual(graph.nodes.flatMap(node => node.members).sort(), plan.graph.nodes.map(node => node.id).sort());
    }
});

test('a full run tracks, triangulates through skeletons, and leaves Blender and exports off when the plan has neither', () => {
    const graph = sectionGraph(settings, plans.full, null);
    const node = (title: string) => graph.nodes.find(item => item.title === title)!;
    assert.equal(node('SkellyTracker').state, 'will run');
    assert.deepEqual(node('SkellyTracker').bars.map(bar => bar.label), ['Detect poses', 'Annotate videos', 'Save 2D tracking']);
    assert.deepEqual(node('SkellyForge').bars.map(bar => bar.label),
        ['Triangulation', 'Gap filling and filtering', 'Person scale fitting', 'Skeleton reconstruction']);
    assert.equal(node('Blender add-on').state, 'off');
    assert.equal(node('Exports').state, 'off');
    assert.equal(node('Recording').disk.text, 'reads 3 videos · calibration');
});

test('starting from saved 3D points skips tracking and reads nothing from the recording', () => {
    const graph = sectionGraph(settings, plans.fromFiltering, null);
    const node = (title: string) => graph.nodes.find(item => item.title === title)!;
    assert.equal(node('SkellyTracker').state, 'not run');
    assert.equal(node('Recording').state, 'not run');
    assert.equal(node('SkellyForge').state, 'will run');
    assert.ok(graph.wires.filter(wire => wire.target === 'tracker').every(wire => !wire.active));
});

test('a run shows each stage from its operations without inventing progress', () => {
    const plan = plans.full;
    const states: Record<string, Partial<TaskOperation>> = {
        load_and_track: {status: 'complete', progress_fraction: 1, completed: 2700, total: 2700},
        match_and_triangulate: {status: 'running', progress_fraction: 0.3, completed: 270, total: 900},
        align_reference: {status: 'waiting'},
    };
    const run: LaunchedRun = {taskId: 'task', status: 'running', plan, cameras: [],
        operations: plan.topological_order.map(id => operation(id, states[id] ?? (id.startsWith('annotate') || id === 'observation_request' || id === 'save_observations' ? {status: 'complete'} : {})))};
    const graph = sectionGraph(settings, null, run);
    const node = (title: string) => graph.nodes.find(item => item.title === title)!;
    assert.equal(node('SkellyTracker').state, 'complete');
    assert.equal(node('SkellyForge').state, 'running');
    const triangulation = node('SkellyForge').bars.find(bar => bar.label === 'Triangulation')!;
    assert.equal(triangulation.text, '270/900');
    assert.equal(triangulation.fraction, 0.3);
    assert.equal(node('SkellyForge').bars.find(bar => bar.label === 'Person scale fitting')!.fraction, null);
});

test('a run missing an operation for a plan node fails loudly', () => {
    const plan = plans.full;
    const run: LaunchedRun = {taskId: 'task', status: 'running', plan, cameras: [], operations: plan.topological_order.slice(1).map(id => operation(id))};
    assert.throws(() => sectionGraph(settings, null, run), /load_and_track/);
});

type Point = [number, number];
/** The path as short segments: M, L and C commands as the layout writes them. */
function polyline(d: string): Point[] {
    const numbers = (text: string): number[] => text.trim().split(/[\s,]+/).map(Number);
    const points: Point[] = [];
    for (const [, command, args] of d.matchAll(/([MLC])([^MLC]*)/g)) {
        const n = numbers(args);
        if (command === 'M' || command === 'L') points.push([n[0], n[1]]);
        else {
            const [x0, y0] = points[points.length - 1];
            for (let t = 0.05; t <= 1.0001; t += 0.05) {
                const u = 1 - t;
                points.push([u * u * u * x0 + 3 * u * u * t * n[0] + 3 * u * t * t * n[2] + t * t * t * n[4],
                    u * u * u * y0 + 3 * u * u * t * n[1] + 3 * u * t * t * n[3] + t * t * t * n[5]]);
            }
        }
    }
    return points;
}
const cross = (a: Point, b: Point, c: Point, d: Point): boolean => {
    const side = (p: Point, q: Point, r: Point): number => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
    return side(a, b, c) * side(a, b, d) < 0 && side(c, d, a) * side(c, d, b) < 0;
};

test('no two wires cross, and the videos and 2D keypoints wires run straight', () => {
    const graph = sectionGraph({...settings, blender: {...settings.blender, exportAfter: true}}, plans.full, null);
    const layout = sectionLayout(graph);
    const lines = layout.wires.map(wire => ({id: wire.id, points: polyline(wire.d)}));
    for (let i = 0; i < lines.length; i++) {
        for (let j = i + 1; j < lines.length; j++) {
            for (let a = 1; a < lines[i].points.length; a++) {
                for (let b = 1; b < lines[j].points.length; b++) {
                    assert.ok(!cross(lines[i].points[a - 1], lines[i].points[a], lines[j].points[b - 1], lines[j].points[b]),
                        `${lines[i].id} crosses ${lines[j].id}`);
                }
            }
        }
    }
    const node = (id: string) => graph.nodes.find(item => item.id === id)!;
    const y = (id: 'recording' | 'tracker' | 'forge', direction: 'in' | 'out', data: string) => layout.boxes.get(id)!.y + portOffset(node(id), direction, data);
    assert.equal(y('recording', 'out', 'videos'), y('tracker', 'in', 'videos'));
    assert.equal(y('tracker', 'out', 'keypoints2d'), y('forge', 'in', 'keypoints2d'));
});
