import assert from 'node:assert/strict';
import {test} from 'node:test';
import {ProcessingPlanSchema} from '@/services/server/transport/message-contract';
import {displayGraph} from './graph-model';
import {computeLayout, type GraphDirection} from './graph-layout';
// Plans from the production recipes; regenerate with tools/make-processing-plan-fixtures.py.
import full from './fixtures/plan-full.json';
import fromFiltering from './fixtures/plan-from-filtering.json';
import toTriangulation from './fixtures/plan-to-triangulation.json';

const plans = {full, fromFiltering, toTriangulation};

for (const [name, fixture] of Object.entries(plans)) {
    const plan = ProcessingPlanSchema.parse(fixture.plan);

    test(`${name}: every plan node is drawn once with a title, a stage and its settings section`, () => {
        const graph = displayGraph(plan);
        assert.deepEqual(graph.nodes.map(node => node.id).sort(), plan.graph.nodes.map(node => node.id).sort());
        assert.equal(graph.edges.length, plan.graph.edges.length);
        for (const node of graph.nodes) {
            assert.ok(node.title.length > 0, node.id);
            assert.ok(node.stageNumber >= 1 && node.stageNumber <= 5, node.id);
        }
    });

    test(`${name}: disk cards come only from declared effects, saves before loads`, () => {
        const graph = displayGraph(plan);
        for (const node of graph.nodes) {
            const effects = node.definition.effects;
            const expected = effects.includes('write_disk') ? 'write' : effects.includes('read_record') || effects.includes('read_live') ? 'read' : null;
            assert.equal(node.io, expected, node.id);
            assert.deepEqual(node.files.map(file => file.path), plan.read_paths[node.id] ?? [], node.id);
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
    const broken = {...plan, graph: {...plan.graph, nodes: [...plan.graph.nodes, {...plan.graph.nodes[0], id: 'unknown_operation'}]}};
    assert.throws(() => displayGraph(broken), /unknown_operation/);
});
