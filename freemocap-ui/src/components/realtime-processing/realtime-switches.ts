// The realtime pipeline's switch rules, as plain functions of its settings: no React, no store, no server.
// Switches follow the pipeline like posthoc stages. A switch counts only while everything it needs counts, so
// switching a stage off switches off and locks what follows it. Every switch keeps its own setting, so switching
// the stage back on brings what follows back as it was.
import type {RealtimeDetectorType, RealtimePipelineConfig} from '@/store/slices/realtime/realtime-types';
import type {TemporalConfig} from '@/types/temporal-config';

/** The switches as they are set, with what decides whether each one can count. */
export interface RealtimeSwitchInput {
    person: boolean; charuco: boolean; detector: RealtimeDetectorType; dlcGeometry: boolean; filtersLoaded: boolean;
    triangulation: boolean; reconstruction: boolean; filterTrajectories: boolean; fillGaps: boolean;
    outputs: {vmc: boolean; lsl: boolean};
}

/** What runs: each switch while everything it needs runs. A switch whose `can` is false is locked. */
export interface RealtimeSwitchState {
    person: boolean; charuco: boolean; tracking: boolean; triangulation: boolean; filterTrajectories: boolean;
    fillGaps: boolean; reconstruction: boolean; outputs: {vmc: boolean; lsl: boolean};
    can: {charuco: boolean; triangulation: boolean; filtering: boolean; reconstruction: boolean; vmc: boolean; lsl: boolean};
}

/** Works out what runs, in pipeline order. The input is left as it is: it is what comes back. */
export function realtimeSwitchState(input: RealtimeSwitchInput): RealtimeSwitchState {
    const dlc = input.detector === 'dlc';
    // DLC tracks no board.
    const charuco = input.charuco && !dlc;
    const tracking = input.person || charuco;
    const triangulation = input.triangulation && tracking;
    // Gap filling and filtering passes keypoints through when it is off, so nothing after it waits for it.
    const canFilter = triangulation && input.filtersLoaded;
    // With DLC, reconstruction also needs a geometry file: the rule of realtimeExecutionSettings.
    const canReconstruct = triangulation && (!dlc || input.dlcGeometry);
    const reconstruction = input.reconstruction && canReconstruct;
    return {
        person: input.person, charuco, tracking, triangulation,
        filterTrajectories: input.filterTrajectories && canFilter, fillGaps: input.fillGaps && canFilter, reconstruction,
        outputs: {vmc: input.outputs.vmc && reconstruction, lsl: input.outputs.lsl && triangulation},
        can: {charuco: !dlc, triangulation: tracking, filtering: canFilter, reconstruction: canReconstruct,
            vmc: reconstruction, lsl: triangulation},
    };
}

/** Reads the switches from the settings that hold them. Until the filter settings arrive, their switches read off. */
export function switchInputFrom(config: RealtimePipelineConfig, temporal: TemporalConfig | undefined,
    outputsWanted: {vmc: boolean; lsl: boolean}): RealtimeSwitchInput {
    const camera = config.camera_node_config, aggregator = config.aggregator_config;
    return {
        person: camera.skeleton_tracking_enabled, charuco: camera.charuco_tracking_enabled,
        detector: camera.detector_type ?? 'rtmpose', dlcGeometry: Boolean(camera.dlc_geometry_path),
        filtersLoaded: temporal !== undefined,
        triangulation: aggregator.triangulation_enabled, reconstruction: aggregator.skeleton_fitting_enabled,
        filterTrajectories: temporal?.spatial_smoothing.enabled ?? false, fillGaps: (temporal?.gap_duration_s ?? 0) > 0,
        outputs: outputsWanted,
    };
}

/** The pipeline settings with the given switches set, and nothing else changed. */
export function pipelineConfigWith(config: RealtimePipelineConfig,
    change: Partial<Pick<RealtimeSwitchInput, 'person' | 'charuco' | 'triangulation' | 'reconstruction'>>): RealtimePipelineConfig {
    const camera = config.camera_node_config, aggregator = config.aggregator_config;
    return {
        ...config,
        camera_node_config: {
            ...camera,
            skeleton_tracking_enabled: change.person ?? camera.skeleton_tracking_enabled,
            charuco_tracking_enabled: change.charuco ?? camera.charuco_tracking_enabled,
        },
        aggregator_config: {
            ...aggregator,
            triangulation_enabled: change.triangulation ?? aggregator.triangulation_enabled,
            skeleton_fitting_enabled: change.reconstruction ?? aggregator.skeleton_fitting_enabled,
        },
    };
}

/** The filter settings with the given switches set, and nothing else changed. Fill gaps has no flag of its own:
 *  off is a duration of 0, and switching it on from off writes `restoreGapS`, the duration to bring back. */
export function temporalConfigWith(temporal: TemporalConfig,
    change: {filterTrajectories?: boolean; fillGaps?: boolean; imageFilter?: boolean; rejectJumps?: boolean},
    restoreGapS: number): TemporalConfig {
    const filling = temporal.gap_duration_s > 0;
    return {
        ...temporal,
        image_smoothing: {...temporal.image_smoothing, enabled: change.imageFilter ?? temporal.image_smoothing.enabled},
        spatial_smoothing: {...temporal.spatial_smoothing, enabled: change.filterTrajectories ?? temporal.spatial_smoothing.enabled},
        velocity_gate_enabled: change.rejectJumps ?? temporal.velocity_gate_enabled,
        gap_duration_s: change.fillGaps === undefined ? temporal.gap_duration_s
            : !change.fillGaps ? 0
            // Switched on while it is on, it keeps the duration it has.
            : filling ? temporal.gap_duration_s : restoreGapS,
    };
}

/** A stage box over parts: checked when every part is on, partly on when only some are. */
export function stageBox(parts: boolean[]): {checked: boolean; partly: boolean} {
    const on = parts.filter(Boolean).length;
    return {checked: on > 0 && on === parts.length, partly: on > 0 && on < parts.length};
}

/** One streaming output as the server reports it. */
export interface OutputSnapshot {id: string; status: string | null}

const isActive = (output: OutputSnapshot) => output.status === 'idle' || output.status === 'running';

/** What to do so a protocol's outputs follow its switch. `effective` is the switch while everything it needs is on;
 *  `failed` says its last start failed, which is not retried until the switch goes off and on again. */
export function outputAction(effective: boolean, outputs: OutputSnapshot[], failed: boolean): {start: boolean; stop: string[]} {
    const active = outputs.filter(isActive);
    if (!effective) return {start: false, stop: active.map(output => output.id)};
    return {start: active.length === 0 && !failed, stop: []};
}

/** An output found running is one the user wants: its switch turns on instead of the output being stopped. */
export function adoptWish(outputs: OutputSnapshot[]): boolean {
    return outputs.some(isActive);
}
