// Run: node src/components/realtime-processing/run-realtime-processing-tests.mjs
// The posthoc baseline in fixtures/stage-layout.posthoc.json is recorded by the same command with RECORD_BASELINE=1.
// Record it again only when the posthoc layout is meant to change.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {test} from 'node:test';
import {ProcessingPlanSchema} from '@/services/server/transport/message-contract';
import type {ResumeStage} from '@/services/recording/posthoc-processing';
import {type DataKey, type DraftStage, type GraphInputs, type GraphNode, type GraphNodeId, type GraphWire, type StageGraph, stageGraph} from './stage-graph';
import {type Box, type StageLayout, stageLayout} from './stage-layout';
import full from './fixtures/plan-full.json';

// The tests run from freemocap-ui.
const BASELINE = 'src/components/processing-graph/fixtures/stage-layout.posthoc.json';

const runs = (value: DraftStage): Record<ResumeStage, DraftStage> =>
    ({observations: value, triangulation: value, filtering: value, scale_fit: value, reconstruction: value});
/** The inputs stage-graph.test.ts builds its posthoc graph from. */
const inputs: GraphInputs = {stages: runs({runs: true, reusedFrom: null}), blenderOn: false, blenderFound: true, exportsOn: false,
    exportChannels: ['LANDMARKS_3D'], plan: ProcessingPlanSchema.parse(full.plan), run: null};
const MEASURED = {recording: 120, observations: 410, triangulation: 300, filtering: 260, scale_fit: 150, reconstruction: 180, blender: 220, exports: 200};
const plain = (layout: StageLayout) => ({boxes: [...layout.boxes], wires: layout.wires, width: layout.width, height: layout.height});

test('posthoc layout is unchanged', () => {
    const graph = stageGraph(inputs);
    // With every channel exported, each kind of wire into the exports is drawn: over Blender, under it and around it.
    const exporting = stageGraph({...inputs, exportChannels: ['OVERLAY_2D', 'RAW_KEYPOINTS_3D', 'KEYPOINTS_3D', 'SEGMENT_POSES', 'LANDMARKS_3D']});
    const layouts = {
        unmeasured: plain(stageLayout(graph, {})),
        measured: plain(stageLayout(graph, MEASURED)),
        everyExport: plain(stageLayout(exporting, MEASURED)),
    };
    if (process.env.RECORD_BASELINE === '1') fs.writeFileSync(BASELINE, `${JSON.stringify(layouts, null, 2)}\n`);
    assert.deepEqual(layouts, JSON.parse(fs.readFileSync(BASELINE, 'utf8')));
});

const node = (id: GraphNodeId, inputs: DataKey[], outputs: DataKey[]): GraphNode =>
    ({id, inputs, outputs, state: 'will run', provenance: null, bars: [], reads: [], writes: [], saves: [], members: []});
const wire = (data: DataKey, source: GraphNodeId, target: GraphNodeId): GraphWire =>
    ({id: `${source}.${data}>${target}`, data, source, target, active: true});
/** The realtime pipeline: the cameras and stages 1-3, then skeleton reconstruction and the two streaming outputs. */
const REALTIME: StageGraph = {
    nodes: [
        node('cameras', [], ['calibration', 'frames']),
        node('observations', ['frames'], ['keypoints2d']),
        node('triangulation', ['calibration', 'keypoints2d'], ['raw3d']),
        node('filtering', ['raw3d'], ['filtered3d']),
        node('reconstruction', ['filtered3d'], ['segments', 'landmarks']),
        node('vmc', ['segments'], ['vmc']),
        node('lsl', ['filtered3d', 'segments', 'landmarks'], ['lsl']),
    ],
    wires: [
        wire('calibration', 'cameras', 'triangulation'), wire('frames', 'cameras', 'observations'),
        wire('keypoints2d', 'observations', 'triangulation'), wire('raw3d', 'triangulation', 'filtering'),
        wire('filtered3d', 'filtering', 'reconstruction'), wire('filtered3d', 'filtering', 'lsl'),
        wire('segments', 'reconstruction', 'vmc'), wire('segments', 'reconstruction', 'lsl'),
        wire('landmarks', 'reconstruction', 'lsl'),
    ],
};
const ROW_ONE: GraphNodeId[] = ['cameras', 'observations', 'triangulation', 'filtering'];
const ROW_TWO: GraphNodeId[] = ['reconstruction', 'vmc', 'lsl'];

test('a seven-node realtime graph lays out in two rows', () => {
    const layout = stageLayout(REALTIME, {});
    const box = (id: GraphNodeId): Box => {
        const found = layout.boxes.get(id);
        assert.ok(found, `no box for ${id}`);
        return found;
    };
    const row1 = ROW_ONE.map(box);
    const row2 = ROW_TWO.map(box);
    assert.deepEqual(row1.map(item => item.y), row1.map(() => row1[0].y), 'row one shares one y');
    assert.deepEqual(row2.map(item => item.y), row2.map(() => row2[0].y), 'row two shares one y');
    assert.ok(row2[0].y > Math.max(...row1.map(item => item.y + item.h)), 'row two starts below row one');
    assert.equal(box('cameras').x, box('reconstruction').x);
    // The calibration wire loops over 2D tracking, level for the stretch its line command draws.
    const calibration = layout.wires.find(item => item.id === 'cameras.calibration>triangulation');
    assert.ok(calibration, 'no calibration wire');
    const level = calibration.d.match(/L[\d.]+,([\d.]+)/);
    assert.ok(level, calibration.d);
    assert.equal(Number(level[1]), box('observations').y - 24);
});
