// The processing graph as the window's sections: the recording, the five processing stages, then Blender
// and the exports. Plan nodes belong to a section by their stage, except the Blender and export nodes.
// Draft states come from the stage controls; run states, progress and saved files from the task's operations.
import type {ProcessingPlan} from '@/services/recording/processing-plan';
import type {TaskOperation} from '@/services/server/transport/message-contract';
import type {ExportChannelKind} from '@/types/recording-exports';
import {PROCESSING_STAGES, type ResumeStage} from '@/services/recording/posthoc-processing';
import {ANNOTATION, basename, type CameraProgress, type LaunchedRun, type OperationState} from './graph-model';

export type NodeId = 'recording' | ResumeStage | 'blender' | 'exports';
export type DataKey = 'calibration' | 'videos' | 'keypoints2d' | 'annotated' | 'raw3d' | 'filtered3d' | 'dimensions'
    | 'segments' | 'landmarks' | 'blend' | 'files';

/** Data on the wires, named as the Exports section's "Data to export" names it where it is exportable. */
export const DATA: Record<DataKey, {name: string; detail: string; colour: string}> = {
    calibration: {name: 'Camera calibration', detail: '.toml', colour: 'var(--graph-type-5)'},
    videos: {name: 'Synchronized videos', detail: 'mp4', colour: 'var(--graph-type-1)'},
    keypoints2d: {name: '2D keypoints', detail: '', colour: 'var(--graph-type-3)'},
    annotated: {name: 'Annotated videos', detail: 'mp4', colour: 'var(--graph-type-2)'},
    raw3d: {name: '3D keypoints', detail: 'raw', colour: 'var(--graph-type-4)'},
    filtered3d: {name: '3D keypoints', detail: 'filtered', colour: 'var(--graph-type-6)'},
    dimensions: {name: 'Body dimensions', detail: '', colour: 'var(--graph-type-13)'},
    segments: {name: 'Rigid-body segments', detail: '', colour: 'var(--graph-type-8)'},
    landmarks: {name: '3D landmarks', detail: '', colour: 'var(--graph-type-7)'},
    blend: {name: 'Blender scene', detail: '.blend', colour: 'var(--graph-type-9)'},
    files: {name: 'Export files', detail: '', colour: 'var(--graph-type-10)'},
};

const CHANNEL_DATA: Record<ExportChannelKind, DataKey> = {
    OVERLAY_2D: 'keypoints2d', RAW_KEYPOINTS_3D: 'raw3d', KEYPOINTS_3D: 'filtered3d', SEGMENT_POSES: 'segments', LANDMARKS_3D: 'landmarks',
};
/** Exports' inputs in the order their producers' outputs sit, so their wires keep their order. */
const EXPORT_INPUT_ORDER: DataKey[] = ['keypoints2d', 'raw3d', 'filtered3d', 'segments', 'landmarks'];

export const PORTS: Record<NodeId, {inputs: DataKey[]; outputs: DataKey[]}> = {
    recording: {inputs: [], outputs: ['calibration', 'videos']},
    observations: {inputs: ['videos'], outputs: ['keypoints2d', 'annotated']},
    triangulation: {inputs: ['calibration', 'keypoints2d'], outputs: ['raw3d']},
    filtering: {inputs: ['raw3d'], outputs: ['filtered3d']},
    scale_fit: {inputs: ['filtered3d'], outputs: ['dimensions']},
    reconstruction: {inputs: ['filtered3d', 'dimensions'], outputs: ['segments', 'landmarks']},
    blender: {inputs: ['segments', 'landmarks'], outputs: ['blend']},
    exports: {inputs: [], outputs: ['files']},
};
export const PRODUCER: Record<DataKey, NodeId> = {
    calibration: 'recording', videos: 'recording', keypoints2d: 'observations', annotated: 'observations', raw3d: 'triangulation',
    filtered3d: 'filtering', dimensions: 'scale_fit', segments: 'reconstruction', landmarks: 'reconstruction', blend: 'blender', files: 'exports',
};
export const NODE_ORDER: NodeId[] = ['recording', ...PROCESSING_STAGES.map(([stage]) => stage), 'blender', 'exports'];

/** Draft: what the stage controls ask for. Run: the launched task's operation states. */
export type NodeState = 'will run' | 'reused' | 'not run' | 'off' | 'skipped' | OperationState;

export interface NodeBar {
    label: string;
    state: NodeState;
    /** null: the server reports no measured progress for this work. */
    fraction: number | null;
    text: string;
}

export interface GraphNode {
    id: NodeId;
    inputs: DataKey[];
    outputs: DataKey[];
    state: NodeState;
    /** Where a skipped stage's data comes from, such as "from Run 0". */
    provenance: string | null;
    bars: NodeBar[];
    reads: string[];
    writes: string[];
    /** The files this section saves, as the plan names them before the run reports them. */
    saves: string[];
    members: string[];
}

export interface GraphWire {
    id: string;
    data: DataKey;
    source: NodeId;
    target: NodeId;
    active: boolean;
}

export interface StageGraph {
    nodes: GraphNode[];
    wires: GraphWire[];
}

/** The section a plan node belongs to. */
export function nodeOf(node: ProcessingPlan['graph']['nodes'][number]): NodeId {
    if (node.id === 'blender') return 'blender';
    if (node.id === 'channel_exports' || node.id === 'tall_csv') return 'exports';
    const stage = PROCESSING_STAGES.find(([key]) => key === node.stage)?.[0];
    if (!stage) throw new Error(`Plan node "${node.id}" has no processing stage`);
    return stage;
}

/** One bar from several operations: counts only from the one operation that reports them; no invented progress. */
export function mergedBar(label: string, steps: TaskOperation[]): NodeBar {
    const has = (status: OperationState): boolean => steps.some(step => step.status === status);
    const state: OperationState = has('failed') ? 'failed' : has('cancelled') ? 'cancelled' : has('running') ? 'running'
        : steps.every(step => step.status === 'complete') ? 'complete' : has('complete') ? 'running' : 'waiting';
    const counted = steps.filter(step => step.total !== null && step.completed !== null);
    const one = counted.length === 1 ? counted[0] : null;
    return {label, state, fraction: state === 'complete' ? 1 : one ? one.progress_fraction : null, text: one ? `${one.completed}/${one.total}` : state};
}

export interface DraftStage {
    runs: boolean;
    /** Where a stage that does not run takes its result from, such as "from Run 0"; null when nothing is reused. */
    reusedFrom: string | null;
}

export interface GraphInputs {
    /** Draft state of each processing stage, from the stage controls. */
    stages: Record<ResumeStage, DraftStage>;
    blenderOn: boolean;
    blenderFound: boolean;
    exportsOn: boolean;
    exportChannels: ExportChannelKind[];
    /** The draft plan for the current settings; null while it is built or when it cannot be. */
    plan: ProcessingPlan | null;
    /** The launched run when one is shown. */
    run: LaunchedRun | null;
}

const isLoad = (id: string): boolean => id.startsWith('load_saved_');

export function stageGraph(input: GraphInputs): StageGraph {
    const {run} = input;
    const plan = run ? run.plan : input.plan;
    const operations = run ? new Map(run.operations.map(operation => [operation.operation_id, operation])) : null;
    const live = operations !== null && operations.size > 0;
    const members = Object.fromEntries(NODE_ORDER.map(id => [id, [] as string[]])) as Record<NodeId, string[]>;
    if (plan) for (const id of plan.topological_order) {
        const node = plan.graph.nodes.find(item => item.id === id);
        if (!node) throw new Error(`Plan order names unknown node "${id}"`);
        members[nodeOf(node)].push(id);
    }
    if (live) {
        const missing = plan!.topological_order.filter(id => !operations!.has(id));
        if (missing.length) throw new Error(`Task ${run!.taskId} reports no operation for plan node(s): ${missing.join(', ')}`);
    }
    const effects = (id: string) => plan!.graph.nodes.find(node => node.id === id)!.effects;
    const steps = (ids: string[]): TaskOperation[] => ids.map(id => operations!.get(id)!);
    const reads = (ids: string[]): string[] => [...new Set(ids.flatMap(id => [...(operations?.get(id)?.files_read ?? []), ...(plan?.read_paths[id] ?? [])]))];
    const writes = (ids: string[]): string[] => [...new Set(ids.flatMap(id => operations?.get(id)?.files_written ?? []))];
    const saves = (ids: string[]): string[] => [...new Set(ids.filter(id => effects(id).includes('write_disk')).flatMap(id => plan!.read_paths[id] ?? []))];
    const cameras: CameraProgress[] = run?.cameras ?? [];

    const nodes = NODE_ORDER.map((id): GraphNode => {
        const ids = members[id];
        const base = {id, inputs: id === 'exports'
            ? EXPORT_INPUT_ORDER.filter(data => input.exportChannels.some(channel => CHANNEL_DATA[channel] === data))
            : PORTS[id].inputs, outputs: PORTS[id].outputs, provenance: null, reads: reads(ids), writes: writes(ids),
            saves: plan ? saves(ids) : [], members: ids};
        if (id === 'recording') {
            const used = NODE_ORDER.slice(1).some(node => input.stages[node as ResumeStage]?.runs && ['observations', 'triangulation'].includes(node));
            return {...base, reads: [...(plan?.read_paths.load_and_track ?? []), ...(plan?.read_paths.match_and_triangulate ?? [])],
                state: live ? 'complete' : used ? 'will run' : 'not run', bars: []};
        }
        if (id === 'blender' || id === 'exports') {
            const on = id === 'blender' ? input.blenderOn : input.exportsOn;
            if (!on) return {...base, state: 'off', bars: []};
            if (id === 'blender' && !input.blenderFound) return {...base, state: 'skipped', provenance: 'Blender not found', bars: []};
            if (live && ids.length) {
                const bars = id === 'blender' ? [mergedBar('Export to Blender', steps(ids))]
                    : ids.map(member => mergedBar(member === 'tall_csv' ? 'Tall CSV' : 'Export files', steps([member])));
                return {...base, state: mergedBar('', steps(ids)).state, bars};
            }
            return {...base, state: ids.length || !plan ? 'will run' : 'not run', bars: []};
        }
        const draft = input.stages[id];
        if (!draft.runs) {
            return {...base, state: draft.reusedFrom ? 'reused' : 'not run', provenance: draft.reusedFrom, bars: []};
        }
        if (!live) return {...base, state: ids.length && ids.every(isLoad) ? 'reused' : 'will run', bars: []};
        if (id === 'observations') {
            const track = ids.filter(member => member === 'load_and_track');
            const annotate = ids.filter(member => ANNOTATION.test(member));
            const save = ids.filter(member => member === 'observation_request' || member === 'save_observations');
            const trackState = track.length ? mergedBar('', steps(track)).state : 'waiting';
            const bars = [
                ...(cameras.length
                    ? cameras.map((camera, index) => ({label: `Video ${index + 1}`, state: trackState as NodeState, fraction: camera.fraction,
                        text: camera.fraction === null ? '' : `${Math.round(camera.fraction * 100)}%`}))
                    : track.length ? [mergedBar('Detect poses', steps(track))] : []),
                ...(annotate.length ? [mergedBar('Annotate videos', steps(annotate))] : []),
                ...(save.length ? [mergedBar('Save 2D tracking', steps(save))] : []),
            ];
            return {...base, state: mergedBar('', steps(ids)).state, bars};
        }
        return {...base, state: mergedBar('', steps(ids)).state, bars: [mergedBar(PROCESSING_STAGES.find(([key]) => key === id)![1], steps(ids))]};
    });
    const byId = new Map(nodes.map(node => [node.id, node]));
    const running = (id: NodeId): boolean => !['not run', 'off', 'skipped'].includes(byId.get(id)!.state);
    const wires = nodes.flatMap(node => node.inputs.map((data): GraphWire => ({
        id: `${PRODUCER[data]}.${data}>${node.id}`, data, source: PRODUCER[data], target: node.id,
        active: running(node.id) && (running(PRODUCER[data]) || byId.get(PRODUCER[data])!.state === 'reused'),
    })));
    return {nodes, wires};
}

export {basename};
