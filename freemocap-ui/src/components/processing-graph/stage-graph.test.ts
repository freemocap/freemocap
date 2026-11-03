import assert from 'node:assert/strict';
import {test} from 'node:test';
import {ProcessingPlanSchema, type TaskOperation} from '@/services/server/transport/message-contract';
import type {ResumeStage} from '@/services/recording/posthoc-processing';
import type {LaunchedRun} from './graph-model';
import {type DraftStage, type GraphInputs, NODE_ORDER, stageGraph} from './stage-graph';
import {portOffset, stageLayout} from './stage-layout';
// Plans from the production recipes; regenerate with tools/make-processing-plan-fixtures.py.
import full from './fixtures/plan-full.json';
import fromFiltering from './fixtures/plan-from-filtering.json';
import toTriangulation from './fixtures/plan-to-triangulation.json';

const plans = {full: ProcessingPlanSchema.parse(full.plan), fromFiltering: ProcessingPlanSchema.parse(fromFiltering.plan),
    toTriangulation: ProcessingPlanSchema.parse(toTriangulation.plan)};
const runs = (value: DraftStage): Record<ResumeStage, DraftStage> =>
    ({observations: value, triangulation: value, filtering: value, scale_fit: value, reconstruction: value});
const inputs: GraphInputs = {stages: runs({runs: true, reusedFrom: null}), blenderOn: false, blenderFound: true, exportsOn: false,
    exportChannels: ['LANDMARKS_3D'], plan: plans.full, run: null};
const operation = (id: string, changes: Partial<TaskOperation> = {}): TaskOperation => ({operation_id: id, label: id, status: 'waiting',
    progress_fraction: null, detail: '', completed: null, total: null, unit: null, items: [], elapsed_seconds: null, seconds_per_motion_frame: null, ...changes});

test('the graph has one node per section in order, and every plan node belongs to exactly one', () => {
    for (const plan of Object.values(plans)) {
        const graph = stageGraph({...inputs, plan});
        assert.deepEqual(graph.nodes.map(node => node.id), NODE_ORDER);
        assert.deepEqual(graph.nodes.flatMap(node => node.members).sort(), plan.graph.nodes.map(node => node.id).sort());
    }
});

test('stages that do not run are reused with their provenance, and the recording is not read', () => {
    const stages = {...runs({runs: true, reusedFrom: null}), observations: {runs: false, reusedFrom: 'from Run 0'},
        triangulation: {runs: false, reusedFrom: 'from Run 0'}};
    const graph = stageGraph({...inputs, stages, plan: plans.fromFiltering});
    const node = (id: string) => graph.nodes.find(item => item.id === id)!;
    assert.equal(node('observations').state, 'reused');
    assert.equal(node('observations').provenance, 'from Run 0');
    assert.equal(node('recording').state, 'not run');
    assert.equal(node('filtering').state, 'will run');
    assert.ok(graph.wires.filter(wire => wire.target === 'observations').every(wire => !wire.active));
    assert.ok(graph.wires.find(wire => wire.source === 'triangulation' && wire.target === 'filtering')!.active);
});

test('Blender is off when switched off, and skipped with a reason when the server found no executable', () => {
    const node = (graph: ReturnType<typeof stageGraph>) => graph.nodes.find(item => item.id === 'blender')!;
    assert.equal(node(stageGraph(inputs)).state, 'off');
    const missing = node(stageGraph({...inputs, blenderOn: true, blenderFound: false}));
    assert.equal(missing.state, 'skipped');
    assert.equal(missing.provenance, 'Blender not found');
});

test('exports take one input per chosen channel, in their producers\' order', () => {
    const graph = stageGraph({...inputs, exportsOn: true, exportChannels: ['LANDMARKS_3D', 'OVERLAY_2D', 'KEYPOINTS_3D']});
    assert.deepEqual(graph.nodes.find(node => node.id === 'exports')!.inputs, ['keypoints2d', 'filtered3d', 'landmarks']);
});

test('a run shows each stage from its operations, with one bar per tracked video', () => {
    const plan = plans.full;
    const states: Record<string, Partial<TaskOperation>> = {
        load_and_track: {status: 'complete', progress_fraction: 1, completed: 2700, total: 2700},
        match_and_triangulate: {status: 'running', progress_fraction: 0.3, completed: 270, total: 900},
    };
    const cameras = [0.5, 1].map((fraction, index) => ({cameraId: String(index), fraction, detail: ''}));
    const run: LaunchedRun = {taskId: 'task', status: 'running', plan, cameras,
        operations: plan.topological_order.map(id => operation(id, states[id] ?? (id.startsWith('annotate') || id === 'observation_request' || id === 'save_observations' ? {status: 'complete'} : {})))};
    const graph = stageGraph({...inputs, run});
    const node = (id: string) => graph.nodes.find(item => item.id === id)!;
    assert.equal(node('observations').state, 'complete');
    assert.deepEqual(node('observations').bars.map(bar => bar.label), ['Video 1', 'Video 2', 'Annotate videos', 'Save 2D tracking']);
    assert.equal(node('triangulation').state, 'running');
    assert.equal(node('triangulation').bars[0].text, '270/900');
    assert.equal(node('triangulation').bars[0].fraction, 0.3);
    assert.equal(node('scale_fit').bars[0].fraction, null);
});

test('a run missing an operation for a plan node fails loudly', () => {
    const plan = plans.full;
    const run: LaunchedRun = {taskId: 'task', status: 'running', plan, cameras: [], operations: plan.topological_order.slice(1).map(id => operation(id))};
    assert.throws(() => stageGraph({...inputs, run}), /load_and_track/);
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

test('no two wires cross, and the straight-through wires run level', () => {
    const graph = stageGraph({...inputs, blenderOn: true, exportsOn: true, exportChannels: ['LANDMARKS_3D', 'SEGMENT_POSES']});
    const heights = {recording: 260, observations: 300, triangulation: 420, filtering: 200, scale_fit: 120, reconstruction: 140, blender: 500, exports: 400};
    const layout = stageLayout(graph, heights);
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
    const y = (id: 'recording' | 'observations' | 'triangulation' | 'scale_fit' | 'reconstruction', direction: 'in' | 'out', data: 'videos' | 'keypoints2d' | 'dimensions') =>
        layout.boxes.get(id)!.y + portOffset(node(id), direction, data);
    assert.equal(y('recording', 'out', 'videos'), y('observations', 'in', 'videos'));
    assert.equal(y('scale_fit', 'out', 'dimensions'), y('reconstruction', 'in', 'dimensions'));
});
