// The processing graph as the Mocap panel's sections: Recording → SkellyTracker → SkellyForge → Blender add-on and Exports.
// Settings rows come from the panel's settings; which work runs, what it reads and saves, and its progress come from the
// server's plan and task operations, assigned to a section by plan node id and stage.
import type {ProcessingPlan} from '@/services/recording/processing-plan';
import type {TaskOperation} from '@/services/server/transport/message-contract';
import type {ExportChannelKind} from '@/types/recording-exports';
import {ANNOTATION, basename, type CameraProgress, type LaunchedRun, type OperationState, stageOf} from './graph-model';

export type SectionId = 'recording' | 'tracker' | 'forge' | 'blender' | 'exports';
/** Names of the Mocap panel's settings sections. */
export type PanelSection = 'Recording directory' | 'Processing stages' | 'Detectors' | 'Camera geometry' | 'Triangulation' | 'Post-processing' | 'Blender' | 'Exports';
export type DataKey = 'calibration' | 'videos' | 'keypoints2d' | 'annotated' | 'raw3d' | 'filtered3d' | 'segments' | 'landmarks' | 'blend' | 'files';

/** Data on the wires, named as the panel's "Data to export" names it where it is exportable. */
export const DATA: Record<DataKey, {name: string; detail: string; colour: number}> = {
    calibration: {name: 'Camera calibration', detail: '.toml', colour: 5},
    videos: {name: 'Synchronized videos', detail: 'mp4', colour: 1},
    keypoints2d: {name: '2D keypoints', detail: 'camera observations', colour: 3},
    annotated: {name: 'Annotated videos', detail: 'mp4', colour: 2},
    raw3d: {name: '3D keypoints', detail: 'raw triangulated', colour: 4},
    filtered3d: {name: '3D keypoints', detail: 'filtered', colour: 6},
    segments: {name: 'Rigid-body segments', detail: '', colour: 8},
    landmarks: {name: '3D landmarks', detail: '', colour: 7},
    blend: {name: 'Blender scene', detail: '.blend', colour: 9},
    files: {name: 'Export files', detail: '', colour: 10},
};

const CHANNEL_DATA: Record<ExportChannelKind, DataKey> = {
    LANDMARKS_3D: 'landmarks', KEYPOINTS_3D: 'filtered3d', RAW_KEYPOINTS_3D: 'raw3d', OVERLAY_2D: 'keypoints2d', SEGMENT_POSES: 'segments',
};

/** The section that produces each kind of data. */
export const PRODUCER: Record<DataKey, SectionId> = {
    calibration: 'recording', videos: 'recording', keypoints2d: 'tracker', annotated: 'tracker',
    raw3d: 'forge', filtered3d: 'forge', segments: 'forge', landmarks: 'forge', blend: 'blender', files: 'exports',
};

/** The panel's current values, as the panel shows them. */
export interface SectionSettings {
    recordingName: string;
    calibrationFile: string | null;
    detector: string;
    detectorRows: {label: string; value: string}[];
    charuco: boolean;
    alignment: string;
    customTransform: boolean;
    triangulation: {outlierRejection: boolean; minimumCameras: number; maximumDropped: number; targetError: number};
    filter: {enabled: boolean; cutoff: number; order: number};
    blender: {executableFound: boolean; exportAfter: boolean; openWhenDone: boolean; formats: string[]};
    exports: {formats: string[]; exportAfter: boolean; tallCsv: boolean; channels: ExportChannelKind[]};
}

/** draft: what the plan will do; run: the launched task's operation states. */
export type SectionState = 'will run' | 'reused' | 'not run' | 'off' | OperationState;

export interface SectionBar {
    label: string;
    state: SectionState;
    /** null: the server reports no measured progress for this work. */
    fraction: number | null;
    text: string;
}

export interface SectionNode {
    id: SectionId;
    title: string;
    panelSections: PanelSection[];
    state: SectionState | null;
    inputs: DataKey[];
    outputs: DataKey[];
    groups: {heading: string | null; rows: {label: string; value: string}[]}[];
    bars: SectionBar[];
    disk: {direction: 'read' | 'write'; text: string};
    /** Paths the work reads and writes, for the details panel. */
    reads: string[];
    writes: string[];
    /** Plan node ids drawn in this section. */
    members: string[];
}

export interface SectionWire {
    id: string;
    data: DataKey;
    source: SectionId;
    target: SectionId;
    active: boolean;
}

export interface SectionGraph {
    nodes: SectionNode[];
    wires: SectionWire[];
}

/** Exports' inputs in the order their producers' outputs sit, so their wires do not cross. */
const EXPORT_INPUT_ORDER: DataKey[] = ['keypoints2d', 'raw3d', 'filtered3d', 'segments', 'landmarks'];
const BLENDER_NODES = new Set(['blender']);
const EXPORT_NODES = new Set(['channel_exports', 'tall_csv']);
const STAGE_BARS: Record<string, string> = {
    triangulation: 'Triangulation', filtering: 'Gap filling and filtering', scale_fit: 'Person scale fitting', reconstruction: 'Skeleton reconstruction',
};

/** The section each plan node belongs to: exports and Blender by id, 2D tracking by its stage, all later stages SkellyForge. */
export function sectionOf(node: ProcessingPlan['graph']['nodes'][number]): SectionId {
    if (BLENDER_NODES.has(node.id)) return 'blender';
    if (EXPORT_NODES.has(node.id)) return 'exports';
    const {stageNumber} = stageOf(node.stage);
    if (stageNumber === 0) throw new Error(`Plan node "${node.id}" has no processing stage`);
    return stageNumber === 1 ? 'tracker' : 'forge';
}

const isLoad = (id: string): boolean => id.startsWith('load_saved_');
const onOff = (value: boolean): string => value ? 'On' : 'Off';

/** One bar from several operations: no invented progress, counts only from the one operation that reports them. */
function bar(label: string, steps: TaskOperation[]): SectionBar {
    const has = (status: OperationState): boolean => steps.some(step => step.status === status);
    const state: OperationState = has('failed') ? 'failed' : has('cancelled') ? 'cancelled' : has('running') ? 'running'
        : steps.every(step => step.status === 'complete') ? 'complete' : has('complete') ? 'running' : 'waiting';
    const counted = steps.filter(step => step.total !== null && step.completed !== null);
    const one = counted.length === 1 ? counted[0] : null;
    const fraction = state === 'complete' ? 1 : one ? one.progress_fraction : null;
    const text = one ? `${one.completed}/${one.total}` : state;
    return {label, state, fraction, text};
}

function draftBar(label: string, state: SectionState): SectionBar {
    return {label, state, fraction: null, text: state};
}

function memberState(members: string[], operations: Map<string, TaskOperation> | null, offWhenEmpty: boolean): SectionState {
    if (members.length === 0) return offWhenEmpty ? 'off' : 'not run';
    if (!operations || operations.size === 0) return members.every(isLoad) ? 'reused' : 'will run';
    return bar('', members.map(id => operations.get(id)!)).state;
}

/** The five sections for the current settings, with the draft plan or the launched run when there is one. */
export function sectionGraph(settings: SectionSettings, plan: ProcessingPlan | null, run: LaunchedRun | null): SectionGraph {
    const operations = run ? new Map(run.operations.map(operation => [operation.operation_id, operation])) : null;
    const source = run ? run.plan : plan;
    const members: Record<SectionId, string[]> = {recording: [], tracker: [], forge: [], blender: [], exports: []};
    if (source) for (const id of source.topological_order) {
        const node = source.graph.nodes.find(item => item.id === id);
        if (!node) throw new Error(`Plan order names unknown node "${id}"`);
        members[sectionOf(node)].push(id);
    }
    const reads = (ids: string[]): string[] => [...new Set(ids.flatMap(id => [
        ...(operations?.get(id)?.files_read ?? []), ...(source?.read_paths[id] ?? [])]))];
    const writes = (ids: string[]): string[] => [...new Set(ids.flatMap(id => operations?.get(id)?.files_written ?? []))];
    const steps = (ids: string[]): TaskOperation[] => ids.map(id => {
        const operation = operations!.get(id);
        if (!operation) throw new Error(`Task ${run!.taskId} reports no operation for plan node "${id}"`);
        return operation;
    });
    const live = operations !== null && operations.size > 0;
    const missing = live && source ? source.topological_order.filter(id => !operations.has(id)) : [];
    if (missing.length) throw new Error(`Task ${run!.taskId} reports no operation for plan node(s): ${missing.join(', ')}`);
    const state = (section: SectionId, offWhenEmpty: boolean): SectionState | null =>
        source ? memberState(members[section], live ? operations : null, offWhenEmpty) : null;

    // Recording: the videos and calibration this run reads.
    const videos = source?.read_paths.load_and_track ?? [];
    const calibrationPaths = source?.read_paths.match_and_triangulate ?? [];
    const recording: SectionNode = {
        id: 'recording', title: 'Recording', panelSections: ['Recording directory'], state: source ? (videos.length || calibrationPaths.length ? 'will run' : 'not run') : null,
        inputs: [], outputs: ['calibration', 'videos'],
        groups: [{heading: null, rows: [{label: 'Folder', value: settings.recordingName || 'none selected'},
            {label: 'Calibration', value: settings.calibrationFile ?? 'none loaded'},
            ...(videos.length ? [{label: 'Videos', value: `${videos.length}`}] : [])]}],
        bars: [], disk: {direction: 'read', text: videos.length || calibrationPaths.length
            ? `reads ${[videos.length ? `${videos.length} videos` : '', calibrationPaths.length ? 'calibration' : ''].filter(Boolean).join(' · ')}`
            : 'not read this run'},
        reads: [...videos, ...calibrationPaths], writes: [], members: [],
    };
    if (live && recording.state === 'will run') recording.state = 'complete';

    // SkellyTracker: 2D tracking.
    const tracker = members.tracker;
    const annotate = tracker.filter(id => ANNOTATION.test(id));
    const trackerGroups = [
        {label: 'Detect poses', ids: tracker.filter(id => id === 'load_and_track')},
        {label: 'Annotate videos', ids: annotate},
        {label: 'Save 2D tracking', ids: tracker.filter(id => id === 'observation_request' || id === 'save_observations')},
        {label: 'Load saved 2D tracking', ids: tracker.filter(id => id === 'load_saved_observations')},
    ].filter(group => group.ids.length);
    const trackerState = state('tracker', false);
    const cameras: CameraProgress[] = run?.cameras ?? [];
    const trackerBars: SectionBar[] = live
        ? [...(cameras.length
            ? cameras.map((camera, index) => ({label: `Video ${index + 1}`, state: bar('', steps(tracker.filter(id => id === 'load_and_track'))).state,
                fraction: camera.fraction, text: camera.fraction === null ? '' : `${Math.round(camera.fraction * 100)}%`}))
            : trackerGroups.filter(group => group.label === 'Detect poses').map(group => bar(group.label, steps(group.ids)))),
            ...trackerGroups.filter(group => group.label !== 'Detect poses').map(group => bar(group.label, steps(group.ids)))]
        : trackerGroups.map(group => draftBar(group.label, group.ids.every(isLoad) ? 'reused' : 'will run'));
    const trackerNode: SectionNode = {
        id: 'tracker', title: 'SkellyTracker', panelSections: ['Detectors'], state: trackerState,
        inputs: ['videos'], outputs: source && !annotate.length ? ['keypoints2d'] : ['keypoints2d', 'annotated'],
        groups: [{heading: null, rows: [{label: 'Skeleton detector', value: settings.detector}, ...settings.detectorRows,
            {label: 'Detect Charuco board', value: onOff(settings.charuco)}]}],
        bars: trackerBars,
        disk: tracker.length && tracker.every(isLoad)
            ? {direction: 'read', text: 'loads saved 2D tracking'}
            : {direction: 'write', text: tracker.length ? `saves 2D tracking${annotate.length ? ' · annotated videos' : ''}` : 'not run'},
        reads: reads(tracker), writes: writes(tracker), members: tracker,
    };

    // SkellyForge: triangulation onward, one bar per processing stage.
    const forge = members.forge;
    const byStage = new Map<string, string[]>();
    if (source) for (const id of forge) {
        const node = source.graph.nodes.find(item => item.id === id)!;
        byStage.set(node.stage!, [...(byStage.get(node.stage!) ?? []), id]);
    }
    const forgeBars = Object.entries(STAGE_BARS).filter(([stage]) => byStage.has(stage)).map(([stage, label]) => {
        const ids = byStage.get(stage)!;
        return live ? bar(label, steps(ids)) : draftBar(label, ids.every(isLoad) ? 'reused' : 'will run');
    });
    const loads = forge.filter(isLoad);
    const savesTo = [...new Set(['save_spatial', 'save_recording', 'save_stage_result', 'save_model_fits']
        .filter(id => forge.includes(id)).flatMap(id => source?.read_paths[id] ?? []).map(basename))];
    const forgeNode: SectionNode = {
        id: 'forge', title: 'SkellyForge', panelSections: ['Camera geometry', 'Triangulation', 'Post-processing'], state: state('forge', false),
        inputs: ['calibration', 'keypoints2d'], outputs: ['raw3d', 'filtered3d', 'segments', 'landmarks'],
        groups: [
            {heading: 'Camera geometry', rows: [{label: 'Alignment', value: settings.alignment},
                ...(settings.customTransform ? [{label: 'Custom transform', value: 'On'}] : [])]},
            {heading: 'Triangulation', rows: [{label: 'Outlier rejection', value: onOff(settings.triangulation.outlierRejection)},
                ...(settings.triangulation.outlierRejection ? [
                    {label: 'Minimum cameras', value: `${settings.triangulation.minimumCameras}`},
                    {label: 'Maximum cameras to drop', value: `${settings.triangulation.maximumDropped}`},
                    {label: 'Target reprojection error', value: `${settings.triangulation.targetError}`}] : [])]},
            {heading: 'Post-processing', rows: [{label: 'Butterworth filter',
                value: settings.filter.enabled ? `${settings.filter.cutoff} Hz · order ${settings.filter.order}` : 'Off'}]},
        ],
        bars: forgeBars,
        disk: {direction: 'write', text: [loads.length ? 'loads saved results' : '', forge.some(id => id.startsWith('save_'))
            ? `saves 3D results${savesTo.length ? ` → ${savesTo.join(', ')}` : ''}` : ''].filter(Boolean).join(' · ') || 'not run'},
        reads: reads(forge), writes: writes(forge), members: forge,
    };

    // Blender add-on and Exports: run after processing when the plan includes them.
    const blender = members.blender;
    const blenderNode: SectionNode = {
        id: 'blender', title: 'Blender add-on', panelSections: ['Blender'], state: state('blender', true),
        inputs: ['segments', 'landmarks'], outputs: ['blend'],
        groups: [{heading: null, rows: [{label: 'Blender executable', value: settings.blender.executableFound ? 'Found' : 'Not found'},
            {label: 'Export after processing', value: onOff(settings.blender.exportAfter)},
            {label: 'Open .blend when done', value: onOff(settings.blender.openWhenDone)},
            {label: 'Also export', value: settings.blender.formats.length ? settings.blender.formats.join(' · ') : 'none'}]}],
        bars: blender.length ? [live ? bar('Export to Blender', steps(blender)) : draftBar('Export to Blender', 'will run')] : [],
        disk: {direction: 'write', text: blender.length ? `saves ${writes(blender).map(basename).join(', ') || '.blend file'}` : 'off for this run'},
        reads: reads(blender), writes: writes(blender), members: blender,
    };
    const exports = members.exports;
    const exportLabel = (id: string): string => id === 'tall_csv' ? 'Tall CSV' : settings.exports.formats.join(' · ') || 'Export files';
    const exportsNode: SectionNode = {
        id: 'exports', title: 'Exports', panelSections: ['Exports'], state: state('exports', true),
        inputs: EXPORT_INPUT_ORDER.filter(data => settings.exports.channels.some(channel => CHANNEL_DATA[channel] === data)), outputs: ['files'],
        groups: [{heading: null, rows: [{label: 'Formats', value: settings.exports.formats.join(' · ') || 'none'},
            {label: 'Export after processing', value: onOff(settings.exports.exportAfter)},
            {label: 'Tall CSV', value: onOff(settings.exports.tallCsv)}]}],
        bars: exports.map(id => live ? bar(exportLabel(id), steps([id])) : draftBar(exportLabel(id), 'will run')),
        disk: {direction: 'write', text: exports.length ? `saves ${writes(exports).length ? `${writes(exports).length} files` : 'export files'}` : 'off for this run'},
        reads: reads(exports), writes: writes(exports), members: exports,
    };

    const nodes = [recording, trackerNode, forgeNode, blenderNode, exportsNode];
    const byId = new Map(nodes.map(node => [node.id, node]));
    const running = (id: SectionId): boolean => !['not run', 'off'].includes(byId.get(id)!.state ?? '');
    const wires: SectionWire[] = nodes.flatMap(node => node.inputs.map(data => ({
        id: `${PRODUCER[data]}.${data}>${node.id}`, data, source: PRODUCER[data], target: node.id,
        active: running(node.id) && running(PRODUCER[data]),
    })));
    return {nodes, wires};
}
