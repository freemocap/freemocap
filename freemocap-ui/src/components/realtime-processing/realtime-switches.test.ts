// Run: node src/components/realtime-processing/run-realtime-processing-tests.mjs
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {
    type CameraNodeConfig, defaultRealtimePipelineConfig, type RealtimeAggregatorNodeConfig, type RealtimePipelineConfig,
} from '@/store/slices/realtime/realtime-types';
import type {TemporalConfig} from '@/types/temporal-config';
import {
    adoptWish, outputAction, pipelineConfigWith, type RealtimeSwitchInput, type RealtimeSwitchState, realtimeSwitchState,
    stageBox, switchInputFrom, temporalConfigWith,
} from './realtime-switches';

/** Every switch on, with nothing in its way. */
const ON: RealtimeSwitchInput = {
    person: true, charuco: true, detector: 'rtmpose', dlcGeometry: false, filtersLoaded: true,
    triangulation: true, reconstruction: true, filterTrajectories: true, fillGaps: true,
    outputs: {vmc: true, lsl: true},
};
/** What runs then: everything, and no switch is locked. */
const ALL_ON: RealtimeSwitchState = {
    person: true, charuco: true, tracking: true, triangulation: true, filterTrajectories: true, fillGaps: true,
    reconstruction: true, outputs: {vmc: true, lsl: true},
    can: {charuco: true, triangulation: true, filtering: true, reconstruction: true, vmc: true, lsl: true},
};

test('triangulation off switches off and locks everything after it', () => {
    assert.deepEqual(realtimeSwitchState(ON), ALL_ON);
    assert.deepEqual(realtimeSwitchState({...ON, triangulation: false}), {
        ...ALL_ON, triangulation: false, filterTrajectories: false, fillGaps: false, reconstruction: false,
        outputs: {vmc: false, lsl: false},
        can: {...ALL_ON.can, filtering: false, reconstruction: false, vmc: false, lsl: false},
    });
});

test('turning triangulation back on restores what was on', () => {
    // LSL was not wanted, so it stays off; everything that was on comes back.
    const input: RealtimeSwitchInput = {...ON, outputs: {vmc: true, lsl: false}};
    const before = realtimeSwitchState(input);
    assert.equal(realtimeSwitchState({...input, triangulation: false}).outputs.vmc, false);
    const back = realtimeSwitchState({...input, triangulation: true});
    assert.deepEqual(back, before);
    assert.deepEqual(back, {...ALL_ON, outputs: {vmc: true, lsl: false}});
});

test('no tracker locks triangulation', () => {
    const state = realtimeSwitchState({...ON, person: false, charuco: false});
    assert.equal(state.tracking, false);
    assert.equal(state.can.triangulation, false);
    assert.equal(state.triangulation, false);
});

test('the board alone feeds triangulation', () => {
    const state = realtimeSwitchState({...ON, person: false, charuco: true});
    assert.equal(state.can.triangulation, true);
    assert.equal(state.triangulation, true);
});

test('DLC has no board and needs a geometry file to reconstruct', () => {
    const state = realtimeSwitchState({...ON, detector: 'dlc', charuco: true, dlcGeometry: false});
    assert.equal(state.charuco, false);
    assert.equal(state.can.charuco, false);
    assert.equal(state.can.reconstruction, false);
    assert.equal(state.reconstruction, false);
    assert.equal(state.outputs.vmc, false);
    assert.equal(realtimeSwitchState({...ON, detector: 'dlc', charuco: true, dlcGeometry: true}).reconstruction, true);
    // A board DLC cannot track feeds nothing: on its own it leaves triangulation locked.
    assert.equal(realtimeSwitchState({...ON, detector: 'dlc', person: false, charuco: true, dlcGeometry: true}).can.triangulation, false);
});

test('filters lock until their settings load', () => {
    const state = realtimeSwitchState({...ON, filtersLoaded: false});
    assert.equal(state.can.filtering, false);
    assert.equal(state.filterTrajectories, false);
    assert.equal(state.fillGaps, false);
    assert.equal(state.reconstruction, true);
});

test('filtering passes through', () => {
    const state = realtimeSwitchState({...ON, filterTrajectories: false, fillGaps: false});
    assert.equal(state.reconstruction, true);
    assert.equal(state.outputs.vmc, true);
});

test('stage boxes', () => {
    assert.deepEqual(stageBox([true, false]), {checked: false, partly: true});
    assert.deepEqual(stageBox([true, true]), {checked: true, partly: false});
    assert.deepEqual(stageBox([false, false]), {checked: false, partly: false});
    // A box over no parts has nothing on.
    assert.deepEqual(stageBox([]), {checked: false, partly: false});
});

/** The backend's filter defaults. */
const TEMPORAL: TemporalConfig = {
    image_smoothing: {enabled: false, min_cutoff: 1, beta: 0.03, d_cutoff: 1},
    spatial_smoothing: {enabled: true, min_cutoff: 1, beta: 0.01, d_cutoff: 1},
    velocity_gate_enabled: true, max_velocity_mm_per_s: 50000, reacquisition_timeout_s: 0.3,
    gap_duration_s: 0.3, prediction_duration_s: 0.1, velocity_half_life_s: 0.08,
    segment_retention_s: 0.3, max_reprojection_error_px: 60, segment_scale_window_frames: 30,
};

test('fill gaps remembers its duration', () => {
    const filling: TemporalConfig = {...TEMPORAL, gap_duration_s: 0.45};
    const off = temporalConfigWith(filling, {fillGaps: false}, 0.45);
    assert.equal(off.gap_duration_s, 0);
    const back = temporalConfigWith(off, {fillGaps: true}, 0.45);
    assert.equal(back.gap_duration_s, 0.45);
    assert.deepEqual(back, filling);
});

test('switching fill gaps on while it is on keeps its duration', () => {
    // A stage box switches every part on; a part that is on already keeps the duration it has.
    assert.equal(temporalConfigWith(TEMPORAL, {fillGaps: true}, 0.45).gap_duration_s, 0.3);
});

test('outputs start, stop and do not retry a failure', () => {
    const nothing = {start: false, stop: []};
    assert.deepEqual(outputAction(true, [], false), {start: true, stop: []});
    assert.deepEqual(outputAction(true, [{id: 'a', status: 'stopped'}], false), {start: true, stop: []});
    // Switched on again after a failure.
    assert.deepEqual(outputAction(true, [{id: 'a', status: 'failed'}], false), {start: true, stop: []});
    assert.deepEqual(outputAction(true, [], true), nothing);
    assert.deepEqual(outputAction(true, [{id: 'a', status: 'failed'}], true), nothing);
    assert.deepEqual(outputAction(true, [{id: 'a', status: 'running'}], false), nothing);
    assert.deepEqual(
        outputAction(false, [{id: 'a', status: 'running'}, {id: 'b', status: 'idle'}, {id: 'c', status: 'failed'}], false),
        {start: false, stop: ['a', 'b']});
});

test('running outputs are adopted', () => {
    assert.equal(adoptWish([{id: 'a', status: 'idle'}]), true);
    assert.equal(adoptWish([{id: 'a', status: 'failed'}]), false);
});

/** The default pipeline: every stage on, RTMPose, no DLC geometry file. */
const CONFIG = defaultRealtimePipelineConfig;
const WANTED = {vmc: false, lsl: true};
const camera = (change: Partial<CameraNodeConfig>): RealtimePipelineConfig =>
    ({...CONFIG, camera_node_config: {...CONFIG.camera_node_config, ...change}});
const aggregator = (change: Partial<RealtimeAggregatorNodeConfig>): RealtimePipelineConfig =>
    ({...CONFIG, aggregator_config: {...CONFIG.aggregator_config, ...change}});

test('switches read their own config fields', () => {
    // From everything on, each field moves exactly one switch.
    const all = switchInputFrom(CONFIG, TEMPORAL, WANTED);
    assert.deepEqual(all, {...ON, outputs: WANTED});
    assert.deepEqual(switchInputFrom(camera({skeleton_tracking_enabled: false}), TEMPORAL, WANTED), {...all, person: false});
    assert.deepEqual(switchInputFrom(camera({charuco_tracking_enabled: false}), TEMPORAL, WANTED), {...all, charuco: false});
    assert.deepEqual(switchInputFrom(camera({detector_type: 'dlc'}), TEMPORAL, WANTED), {...all, detector: 'dlc'});
    assert.deepEqual(switchInputFrom(camera({dlc_geometry_path: 'C:/models/geometry.json'}), TEMPORAL, WANTED), {...all, dlcGeometry: true});
    assert.deepEqual(switchInputFrom(camera({dlc_geometry_path: null}), TEMPORAL, WANTED), all);
    assert.deepEqual(switchInputFrom(aggregator({triangulation_enabled: false}), TEMPORAL, WANTED), {...all, triangulation: false});
    assert.deepEqual(switchInputFrom(aggregator({skeleton_fitting_enabled: false}), TEMPORAL, WANTED), {...all, reconstruction: false});
    assert.deepEqual(
        switchInputFrom(CONFIG, {...TEMPORAL, spatial_smoothing: {...TEMPORAL.spatial_smoothing, enabled: false}}, WANTED),
        {...all, filterTrajectories: false});
    assert.deepEqual(switchInputFrom(CONFIG, {...TEMPORAL, gap_duration_s: 0}, WANTED), {...all, fillGaps: false});
    // A config that names no detector runs the default one.
    assert.equal(switchInputFrom(camera({detector_type: undefined}), TEMPORAL, WANTED).detector, 'rtmpose');
});

test('filter switches read off until their settings load', () => {
    assert.deepEqual(switchInputFrom(CONFIG, undefined, WANTED),
        {...ON, outputs: WANTED, filtersLoaded: false, filterTrajectories: false, fillGaps: false});
});

test('switches write only their own config fields', () => {
    assert.deepEqual(pipelineConfigWith(CONFIG, {person: false}), camera({skeleton_tracking_enabled: false}));
    assert.deepEqual(pipelineConfigWith(CONFIG, {charuco: false}), camera({charuco_tracking_enabled: false}));
    assert.deepEqual(pipelineConfigWith(CONFIG, {triangulation: false}), aggregator({triangulation_enabled: false}));
    assert.deepEqual(pipelineConfigWith(CONFIG, {reconstruction: false}), aggregator({skeleton_fitting_enabled: false}));
    assert.deepEqual(pipelineConfigWith(CONFIG, {}), CONFIG);
    assert.deepEqual(temporalConfigWith(TEMPORAL, {filterTrajectories: false}, 0.45),
        {...TEMPORAL, spatial_smoothing: {...TEMPORAL.spatial_smoothing, enabled: false}});
    assert.deepEqual(temporalConfigWith(TEMPORAL, {imageFilter: true}, 0.45),
        {...TEMPORAL, image_smoothing: {...TEMPORAL.image_smoothing, enabled: true}});
    assert.deepEqual(temporalConfigWith(TEMPORAL, {rejectJumps: false}, 0.45), {...TEMPORAL, velocity_gate_enabled: false});
    assert.deepEqual(temporalConfigWith(TEMPORAL, {}, 0.45), TEMPORAL);
});
