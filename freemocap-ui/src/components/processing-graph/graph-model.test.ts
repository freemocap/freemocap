import assert from 'node:assert/strict';
import {test} from 'node:test';
import {ProcessingPlanSchema} from '@/services/server/transport/message-contract';
import {displayGraph, type LaunchedRun, nodeRun, operationCount, runOperations} from './graph-model';
import {computeLayout, type GraphDirection} from './graph-layout';
// Plans from the production recipes; regenerate with tools/make-processing-plan-fixtures.py.
import full from './fixtures/plan-full.json';
import fromFiltering from './fixtures/plan-from-filtering.json';
import toTriangulation from './fixtures/plan-to-triangulation.json';

const plans = {full, fromFiltering, toTriangulation};

for (const [name, fixture] of Object.entries(plans)) {
    const plan = ProcessingPlanSchema.parse(fixture.plan);

    test(`${name}: every plan node is drawn in exactly one node with a title and a stage`, () => {
        const graph = displayGraph(plan);
        const members = graph.nodes.flatMap(node => node.members.map(member => member.id));
        assert.deepEqual(members.sort(), plan.graph.nodes.map(node => node.id).sort());
        for (const node of graph.nodes) for (const member of node.members) assert.equal(graph.nodeOf.get(member.id), node.id);
        for (const node of graph.nodes) {
            assert.ok(node.title.length > 0, node.id);
            assert.ok(node.stageNumber >= 1 && node.stageNumber <= 5, node.id);
        }
    });

    test(`${name}: disk cards come only from declared effects, saves before loads`, () => {
        const graph = displayGraph(plan);
        for (const node of graph.nodes) {
            const effects = node.members.flatMap(member => member.effects);
            const expected = effects.includes('write_disk') ? 'write' : effects.includes('read_record') || effects.includes('read_live') ? 'read' : null;
            assert.equal(node.io, expected, node.id);
            assert.deepEqual(node.files.map(file => file.path), [...new Set(node.members.flatMap(member => plan.read_paths[member.id] ?? []))], node.id);
        }
    });

    test(`${name}: every slot and wire has a data kind with a colour index`, () => {
        const graph = displayGraph(plan);
        for (const node of graph.nodes) {
            for (const slot of [...node.inputs, ...node.outputs]) assert.ok(graph.kinds.includes(slot.kind), `${node.id}.${slot.name}`);
            for (const slot of node.inputs) assert.ok(slot.from, `${node.id}.${slot.name} is bound`);
        }
        for (const edge of graph.edges) assert.ok(graph.kinds.includes(edge.kind), edge.id);
    });

    for (const direction of ['right', 'down'] as GraphDirection[]) {
        test(`${name}: ${direction} layout places every node without overlap and routes every edge forward`, () => {
            const graph = displayGraph(plan);
            const layout = computeLayout(graph, direction);
            const boxes = [...layout.boxes.entries()];
            assert.equal(boxes.length, graph.nodes.length);
            for (let i = 0; i < boxes.length; i++) {
                for (let j = i + 1; j < boxes.length; j++) {
                    const [ida, a] = boxes[i];
                    const [idb, b] = boxes[j];
                    const overlap = a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
                    assert.ok(!overlap, `${ida} overlaps ${idb}`);
                }
            }
            assert.equal(layout.paths.length, graph.edges.length);
            for (const edge of graph.edges) {
                const source = layout.boxes.get(edge.source)!;
                const target = layout.boxes.get(edge.target)!;
                assert.ok(direction === 'right' ? source.x < target.x : source.y < target.y, edge.id);
            }
        });
    }
}

test('an unknown plan node fails loudly instead of being drawn unnamed', () => {
    const plan = ProcessingPlanSchema.parse(full.plan);
    const broken = {...plan, topological_order: [...plan.topological_order, 'unknown_operation'],
        graph: {...plan.graph, nodes: [...plan.graph.nodes, {...plan.graph.nodes[0], id: 'unknown_operation'}]}};
    assert.throws(() => displayGraph(broken), /unknown_operation/);
});

test('similar work is drawn as one node: annotation and pose detection with one lane per video, prepare and save pairs, fitting', () => {
    const graph = displayGraph(ProcessingPlanSchema.parse(full.plan));
    const titles = graph.nodes.map(node => node.title);
    assert.deepEqual(titles, ['Detect poses in videos', 'Annotate videos', 'Calculate 3D points', 'Save 2D tracking', 'Fill gaps and smooth',
        'Orient to reference', 'Fit body dimensions', 'Save 3D points', 'Reconstruct skeletons', 'Save recording']);
    const byTitle = (title: string) => graph.nodes.find(node => node.title === title)!;
    assert.deepEqual(byTitle('Annotate videos').lanes.map(lane => lane.member), ['annotate_camera_0', 'annotate_camera_1', 'annotate_camera_2']);
    assert.equal(byTitle('Annotate videos').inputs.length, 1);
    assert.equal(byTitle('Detect poses in videos').lanes.length, 3);
    assert.deepEqual(byTitle('Save 2D tracking').members.map(member => member.id), ['observation_request', 'save_observations']);
    assert.deepEqual(byTitle('Fit body dimensions').members.map(member => member.id), ['reconstruction_input', 'fit_model_dimensions']);
});

test('the main work runs in one straight line and saves hang below it', () => {
    const graph = displayGraph(ProcessingPlanSchema.parse(full.plan));
    const layout = computeLayout(graph, 'right');
    const line = graph.nodes.filter(node => node.io !== 'write' && !node.annotation);
    assert.deepEqual(line.map(node => node.title), ['Detect poses in videos', 'Calculate 3D points', 'Fill gaps and smooth',
        'Orient to reference', 'Fit body dimensions', 'Reconstruct skeletons']);
    for (let i = 1; i < line.length; i++) {
        const wire = layout.paths.find(path => path.edge.source === line[i - 1].id && path.edge.target === line[i].id)!;
        const [start, end] = [wire.d.match(/^M[\d.]+,([\d.]+)/)![1], wire.d.match(/([\d.]+)$/)![1]];
        assert.equal(start, end, `${line[i - 1].title} to ${line[i].title} is straight`);
    }
    const lineBottom = Math.max(...line.map(node => layout.boxes.get(node.id)!.y + layout.boxes.get(node.id)!.h));
    for (const node of graph.nodes.filter(item => !line.includes(item))) assert.ok(layout.boxes.get(node.id)!.y > lineBottom, node.title);
});

const operation = (id: string): LaunchedRun['operations'][number] => ({operation_id: id, label: id, status: 'waiting',
    progress_fraction: null, detail: '', completed: null, total: null, unit: null, elapsed_seconds: null, seconds_per_motion_frame: null});

test('a launched run maps every plan node to its operation by id', () => {
    const plan = ProcessingPlanSchema.parse(full.plan);
    const run: LaunchedRun = {taskId: 'task', status: 'running', plan, operations: plan.graph.nodes.map(node => operation(node.id)), cameras: []};
    const operations = runOperations(run);
    for (const node of plan.graph.nodes) assert.equal(operations.get(node.id)?.operation_id, node.id);
});

test('a queued run with no operations yet draws every node waiting', () => {
    const plan = ProcessingPlanSchema.parse(full.plan);
    assert.equal(runOperations({taskId: 'task', status: 'queued', plan, operations: [], cameras: []}).size, 0);
});

test('a run missing an operation for a plan node fails loudly', () => {
    const plan = ProcessingPlanSchema.parse(full.plan);
    const operations = plan.graph.nodes.slice(1).map(node => operation(node.id));
    assert.throws(() => runOperations({taskId: 'task', status: 'running', plan, operations, cameras: []}), new RegExp(plan.graph.nodes[0].id));
});

test('operation counts carry their unit, then fall back to elapsed time', () => {
    assert.equal(operationCount({...operation('a'), completed: 120, total: 900, unit: 'camera images'}), '120/900 camera images');
    assert.equal(operationCount({...operation('a'), elapsed_seconds: 3.25}), '3.3 s');
    assert.equal(operationCount(operation('a')), '');
});

test('a merged node adds lane counts only when every video reports them, and shows each video', () => {
    const plan = ProcessingPlanSchema.parse(full.plan);
    const graph = displayGraph(plan);
    const annotate = graph.nodes.find(node => node.title === 'Annotate videos')!;
    const counted = (id: string, completed: number) => ({...operation(id), status: 'running' as const, completed, total: 900, unit: 'motion frames', progress_fraction: completed / 900});
    const operations = new Map(plan.graph.nodes.map(node => [node.id, operation(node.id)]));
    operations.set('annotate_camera_0', counted('annotate_camera_0', 300));
    operations.set('annotate_camera_1', counted('annotate_camera_1', 600));
    operations.set('annotate_camera_2', counted('annotate_camera_2', 0));
    const run = nodeRun(annotate, graph, operations, [])!;
    assert.equal(run.summary.status, 'running');
    assert.equal(run.summary.completed, 900);
    assert.equal(run.summary.total, 2700);
    assert.deepEqual(run.lanes.map(lane => lane.text), ['300/900', '600/900', '0/900']);
    operations.set('annotate_camera_2', operation('annotate_camera_2'));
    assert.equal(nodeRun(annotate, graph, operations, [])!.summary.total, null, 'a video without counts leaves the total unknown');
});
