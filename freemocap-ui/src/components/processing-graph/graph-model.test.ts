import assert from 'node:assert/strict';
import {test} from 'node:test';
import {ProcessingPlanSchema} from '@/services/server/transport/message-contract';
import {describeFiles, displayGraph} from './graph-model';
import {computeLayout} from './graph-layout';
// Plans from the production recipes; regenerate with tools/make-processing-plan-fixtures.py.
import full from './fixtures/plan-full.json';
import fromFiltering from './fixtures/plan-from-filtering.json';
import toTriangulation from './fixtures/plan-to-triangulation.json';

const plans = {full, fromFiltering, toTriangulation};

for (const [name, fixture] of Object.entries(plans)) {
    const plan = ProcessingPlanSchema.parse(fixture.plan);

    test(`${name}: every plan node is drawn with a title and its settings section`, () => {
        const graph = displayGraph(plan);
        const operations = graph.nodes.filter(node => node.role === 'operation');
        assert.deepEqual(operations.map(node => node.id).sort(), plan.graph.nodes.map(node => node.id).sort());
        for (const node of operations) {
            assert.ok(node.title.length > 0, node.id);
            assert.ok(node.section !== null, node.id);
        }
    });

    test(`${name}: sources and sinks come only from declared effects`, () => {
        const graph = displayGraph(plan);
        for (const node of plan.graph.nodes) {
            for (const effect of node.effects) {
                const terminal = graph.nodes.find(item => item.id === `${effect}:${node.id}`);
                assert.ok(terminal, `${effect} terminal for ${node.id}`);
                assert.equal(terminal.role, effect === 'read_record' || effect === 'read_live' ? 'source' : 'sink');
            }
        }
        const terminals = graph.nodes.filter(node => node.role !== 'operation');
        assert.equal(terminals.length, plan.graph.nodes.reduce((sum, node) => sum + node.effects.length, 0));
        assert.equal(graph.edges.length, plan.graph.edges.length + terminals.length);
    });

    test(`${name}: layout places every node without overlap and routes every edge`, () => {
        const graph = displayGraph(plan);
        const layout = computeLayout(graph);
        const boxes = [...layout.boxes.values()];
        assert.equal(boxes.length, graph.nodes.length);
        for (let i = 0; i < boxes.length; i++) {
            for (let j = i + 1; j < boxes.length; j++) {
                const a = boxes[i];
                const b = boxes[j];
                const overlap = a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
                assert.ok(!overlap, `boxes ${i} and ${j} overlap`);
            }
        }
        assert.equal(layout.paths.length, graph.edges.length);
        for (const {d} of layout.paths) assert.match(d, /^M-?\d/);
        // Data flows left to right: every edge leaves its source to the right of where it enters its target's layer.
        for (const edge of graph.edges) assert.ok(layout.boxes.get(edge.source)!.x < layout.boxes.get(edge.target)!.x, edge.id);
    });
}

test('read sources are named by file, or by count when there are several videos', () => {
    assert.equal(describeFiles(['/r/a/data.parquet']), 'data.parquet');
    assert.equal(describeFiles(['/r/v/Cam1.mp4', '/r/v/Cam2.mp4', '/r/v/Cam3.mp4']), '3 videos');
    assert.equal(describeFiles(['/r/a.parquet', '/r/b.toml']), '2 files');
});

test('an unknown plan node fails loudly instead of being drawn unnamed', () => {
    const plan = ProcessingPlanSchema.parse(full.plan);
    const broken = {...plan, graph: {...plan.graph, nodes: [...plan.graph.nodes, {...plan.graph.nodes[0], id: 'unknown_operation'}]}};
    assert.throws(() => displayGraph(broken), /unknown_operation/);
});
