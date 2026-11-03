import type {ProcessingPlan} from '@/services/recording/processing-plan';
import type {TaskOperation} from '@/services/server/transport/message-contract';
import {PROCESSING_STAGES} from '@/services/recording/posthoc-processing';

type PlanNode = ProcessingPlan['graph']['nodes'][number];

/** The settings section that holds a node's configuration, named as in the mocap processing window. */
export type SettingsSectionName = 'Processing stages' | 'Detectors' | 'Camera geometry' | 'Triangulation'
    | 'Post-processing' | 'Exports' | 'Blender';

export interface DisplaySlot {
    name: string;
    /** The data contract kind; slots and wires of one kind share a colour. */
    kind: string;
    /** The node feeding an input slot. */
    from: string | null;
}

export interface DiskFile {
    name: string;
    path: string;
}

/** One progress lane on a node: one per video. */
export interface DisplayLane {
    label: string;
    /** The plan node whose operation this lane shows (annotation: one node per video). */
    member: string | null;
    /** The reported camera this lane shows, by position (pose detection: one camera per video). */
    cameraIndex: number | null;
}

/** A node as drawn: one or more plan nodes doing one piece of work, with a disk card when it loads or saves. */
export interface DisplayNode {
    id: string;
    title: string;
    resource: string;
    stageNumber: number;
    stageLabel: string;
    annotation: boolean;
    /** Saves win over loads: a node that reads and writes the recording file is a save. */
    io: 'read' | 'write' | null;
    files: DiskFile[];
    inputs: DisplaySlot[];
    outputs: DisplaySlot[];
    section: SettingsSectionName;
    settings: string[];
    /** The plan nodes drawn as this node, in the plan's topological order. */
    members: PlanNode[];
    lanes: DisplayLane[];
}

export interface DisplayEdge {
    id: string;
    source: string;
    sourceSlot: string;
    target: string;
    targetSlot: string;
    kind: string;
    annotation: boolean;
}

export interface DisplayGraph {
    nodes: DisplayNode[];
    edges: DisplayEdge[];
    /** The drawn node for each plan node id. */
    nodeOf: Map<string, string>;
    /** Data kinds in order of first appearance; a kind's index picks its colour. */
    kinds: string[];
}

const TITLES: Record<string, string> = {
    load_and_track: 'Detect poses in videos',
    load_saved_observations: 'Load saved 2D tracking',
    load_saved_spatial: 'Load saved 3D points',
    load_saved_model_fits: 'Load saved body dimensions',
    match_and_triangulate: 'Calculate 3D points',
    filter_trajectories: 'Fill gaps and smooth',
    align_reference: 'Orient to reference',
    reconstruction_input: 'Prepare for fitting',
    fit_model_dimensions: 'Fit body dimensions',
    reconstruct_skeletons: 'Reconstruct skeletons',
    observation_request: 'Prepare 2D for saving',
    save_observations: 'Save 2D tracking',
    spatial_request: 'Prepare 3D for saving',
    save_spatial: 'Save 3D points',
    save_recording: 'Save recording',
    stage_result_request: 'Prepare results for saving',
    save_stage_result: 'Save requested stages',
    save_model_fits: 'Save body dimensions',
    export_recording: 'Save export files',
    channel_exports: 'Save export files',
    export_tall_csv: 'Save tall CSV',
    tall_csv: 'Save tall CSV',
    blender: 'Export to Blender',
};

const SECTIONS: Record<string, SettingsSectionName> = {
    load_and_track: 'Detectors',
    load_saved_observations: 'Processing stages',
    load_saved_spatial: 'Processing stages',
    load_saved_model_fits: 'Processing stages',
    match_and_triangulate: 'Triangulation',
    align_reference: 'Camera geometry',
    filter_trajectories: 'Post-processing',
    reconstruction_input: 'Post-processing',
    fit_model_dimensions: 'Post-processing',
    reconstruct_skeletons: 'Post-processing',
    observation_request: 'Processing stages',
    save_observations: 'Processing stages',
    spatial_request: 'Camera geometry',
    save_spatial: 'Processing stages',
    save_recording: 'Processing stages',
    stage_result_request: 'Processing stages',
    save_stage_result: 'Processing stages',
    save_model_fits: 'Processing stages',
    export_recording: 'Exports',
    channel_exports: 'Exports',
    export_tall_csv: 'Exports',
    tall_csv: 'Exports',
    blender: 'Blender',
};

/** Request fields each operation reads (mocap_task_config.py names), shown in the inspector. */
const SETTINGS: Record<string, string[]> = {
    load_and_track: ['detectorType', 'rtmPoseModelName', 'rtmPoseConfidenceThreshold', 'executionProvider', 'charucoTrackingEnabled', 'charucoBoard', 'videoFps'],
    annotate: ['detectorType', 'rtmPoseModelName', 'rtmPoseConfidenceThreshold', 'graphAnnotate'],
    match_and_triangulate: ['cameraMatching', 'triangulationConfig', 'calibrationTomlPath'],
    filter_trajectories: ['filterConfig'],
    align_reference: ['bodyAlignment', 'anchorSegmentName', 'detectorType'],
    reconstruction_input: ['anchorSegmentName', 'detectorType', 'charucoBoard'],
    fit_model_dimensions: ['anchorSegmentName', 'detectorType'],
    reconstruct_skeletons: ['anchorSegmentName', 'detectorType'],
    observation_request: ['detectorType', 'baseRunId', 'startStage'],
    save_observations: ['startStage', 'baseRunId', 'runSaveMode'],
    spatial_request: ['bodyAlignment.additional_transform'],
    save_spatial: ['baseRunId', 'runSaveMode'],
    save_recording: ['calibrationTomlPath', 'baseRunId', 'runSaveMode'],
    load_saved_observations: ['baseRunId', 'sensorGroup'],
    load_saved_spatial: ['baseRunId', 'sensorGroup'],
    load_saved_model_fits: ['baseRunId', 'sensorGroup'],
    save_stage_result: ['startStage', 'stopStage', 'runSaveMode'],
    save_model_fits: ['baseRunId', 'runSaveMode'],
    stage_result_request: ['stopStage'],
    channel_exports: ['exportOptions'],
    export_recording: ['exportOptions'],
    tall_csv: ['exportTallCsv'],
    export_tall_csv: ['exportTallCsv'],
    blender: ['exportToBlender', 'blenderImportRoute', 'blenderExportConfig', 'autoOpenBlendFile'],
};

const ANNOTATION = /^annotate_camera_(\d+)$/;

export function nodeTitle(id: string): string {
    const annotation = ANNOTATION.exec(id);
    if (annotation) return `Annotate video ${Number(annotation[1]) + 1}`;
    const title = TITLES[id];
    if (!title) throw new Error(`The graph view has no title for plan node "${id}"`);
    return title;
}

export function nodeSection(id: string): SettingsSectionName {
    if (ANNOTATION.test(id)) return 'Detectors';
    const section = SECTIONS[id];
    if (!section) throw new Error(`The graph view has no settings section for plan node "${id}"`);
    return section;
}

function stageOf(stage: string | null): {stageNumber: number; stageLabel: string} {
    if (stage === null) return {stageNumber: 0, stageLabel: ''};
    const index = PROCESSING_STAGES.findIndex(([key]) => key === stage);
    if (index < 0) throw new Error(`Unknown processing stage "${stage}"`);
    return {stageNumber: index + 1, stageLabel: PROCESSING_STAGES[index][1]};
}

export const basename = (path: string): string => path.split(/[\\/]/).filter(Boolean).pop() ?? path;

/** Plan nodes drawn together as one node. A group present with one member is drawn as that plan node. */
const GROUPS: {id: string; title: string; match: (id: string) => boolean}[] = [
    {id: 'annotate_videos', title: 'Annotate videos', match: id => ANNOTATION.test(id)},
    {id: 'save_2d_tracking', title: 'Save 2D tracking', match: id => id === 'observation_request' || id === 'save_observations'},
    {id: 'save_3d_points', title: 'Save 3D points', match: id => id === 'spatial_request' || id === 'save_spatial'},
    {id: 'fit_body_dimensions', title: 'Fit body dimensions', match: id => id === 'reconstruction_input' || id === 'fit_model_dimensions'},
    {id: 'save_requested_stages', title: 'Save requested stages', match: id => id === 'stage_result_request' || id === 'save_stage_result'},
];

interface ExternalSlot {key: string; name: string; kind: string; from: string | null}

/** A group's slots: member ports wired outside the group, identical ones merged, colliding names replaced by their kind. */
function groupSlots(slots: ExternalSlot[]): {slots: DisplaySlot[]; names: Map<string, string>} {
    const unique: ExternalSlot[] = [];
    for (const slot of slots) {
        if (!unique.some(other => other.name === slot.name && other.kind === slot.kind && other.from === slot.from)) unique.push(slot);
    }
    const label = (slot: ExternalSlot): string => unique.filter(other => other.name === slot.name).length > 1 ? slot.kind : slot.name;
    const names = new Map(slots.map(slot => [slot.key, label(slot)]));
    const drawn: DisplaySlot[] = [];
    for (const slot of unique) {
        if (!drawn.some(other => other.name === label(slot))) drawn.push({name: label(slot), kind: slot.kind, from: slot.from});
    }
    return {slots: drawn, names};
}

/** The plan as drawn. Disk cards come only from declared effects and the plan's read paths. */
export function displayGraph(plan: ProcessingPlan): DisplayGraph {
    const kinds: string[] = [];
    const note = (kind: string): void => {
        if (!kinds.includes(kind)) kinds.push(kind);
    };
    const planNodes = new Map(plan.graph.nodes.map(node => [node.id, node]));
    const order = plan.topological_order.map(id => {
        const node = planNodes.get(id);
        if (!node) throw new Error(`Plan order names unknown node "${id}"`);
        return node;
    });
    if (order.length !== plan.graph.nodes.length) throw new Error('Plan order does not list every plan node once');
    const memberLists = new Map<string, PlanNode[]>();
    const nodeOf = new Map<string, string>();
    for (const node of order) {
        const group = GROUPS.find(candidate => candidate.match(node.id));
        const id = group ? group.id : node.id;
        nodeOf.set(node.id, id);
        memberLists.set(id, [...(memberLists.get(id) ?? []), node]);
    }
    for (const [id, members] of memberLists) {
        if (members.length === 1 && !ANNOTATION.test(members[0].id) && id !== members[0].id) {
            memberLists.delete(id);
            memberLists.set(members[0].id, members);
            nodeOf.set(members[0].id, members[0].id);
        }
    }
    const portKind = (node: string, port: string, direction: 'inputs' | 'outputs'): string => {
        const found = planNodes.get(node)?.[direction].find(item => item.name === port);
        if (!found) throw new Error(`Plan edge uses unknown slot "${node}.${port}"`);
        return found.contract.kind;
    };
    const inputSlots = new Map<string, {slots: DisplaySlot[]; names: Map<string, string>}>();
    const outputSlots = new Map<string, {slots: DisplaySlot[]; names: Map<string, string>}>();
    for (const [id, members] of memberLists) {
        const inside = new Set(members.map(member => member.id));
        const ins: ExternalSlot[] = [];
        const outs: ExternalSlot[] = [];
        for (const member of members) {
            for (const port of member.inputs) {
                const feeds = plan.graph.edges.filter(edge => edge.target.node === member.id && edge.target.port === port.name);
                if (feeds.some(edge => inside.has(edge.source.node))) continue;
                ins.push({key: `${member.id}.${port.name}`, name: port.name, kind: port.contract.kind,
                    from: feeds.length ? nodeOf.get(feeds[0].source.node)! : null});
            }
            for (const port of member.outputs) {
                const uses = plan.graph.edges.filter(edge => edge.source.node === member.id && edge.source.port === port.name);
                if (uses.length && uses.every(edge => inside.has(edge.target.node))) continue;
                outs.push({key: `${member.id}.${port.name}`, name: port.name, kind: port.contract.kind, from: null});
            }
        }
        inputSlots.set(id, groupSlots(ins));
        outputSlots.set(id, groupSlots(outs));
    }
    const edges: DisplayEdge[] = [];
    for (const edge of plan.graph.edges) {
        const source = nodeOf.get(edge.source.node);
        const target = nodeOf.get(edge.target.node);
        if (!source) throw new Error(`Plan edge from unknown node "${edge.source.node}"`);
        if (!target) throw new Error(`Plan edge to unknown node "${edge.target.node}"`);
        if (source === target) continue;
        const sourceSlot = outputSlots.get(source)!.names.get(`${edge.source.node}.${edge.source.port}`)!;
        const targetSlot = inputSlots.get(target)!.names.get(`${edge.target.node}.${edge.target.port}`)!;
        const id = `${source}.${sourceSlot}>${target}.${targetSlot}`;
        if (edges.some(other => other.id === id)) continue;
        edges.push({id, source, sourceSlot, target, targetSlot, kind: portKind(edge.source.node, edge.source.port, 'outputs'),
            annotation: ANNOTATION.test(edge.target.node)});
    }
    const position = new Map(plan.topological_order.map((id, index) => [id, index]));
    const nodes = [...memberLists.entries()].sort(([, a], [, b]) => position.get(a[0].id)! - position.get(b[0].id)!).map(([id, members]): DisplayNode => {
        const first = members[0];
        const effects = members.flatMap(member => member.effects);
        const annotation = members.some(member => ANNOTATION.test(member.id));
        const io = effects.includes('write_disk') ? 'write' : effects.includes('read_record') || effects.includes('read_live') ? 'read' : null;
        const paths = [...new Set(members.flatMap(member => plan.read_paths[member.id] ?? []))];
        const inputs = inputSlots.get(id)!.slots;
        const outputs = outputSlots.get(id)!.slots;
        inputs.forEach(slot => note(slot.kind));
        outputs.forEach(slot => note(slot.kind));
        const group = GROUPS.find(candidate => candidate.id === id);
        const lanes: DisplayLane[] = annotation
            ? members.map(member => ({label: `Video ${Number(ANNOTATION.exec(member.id)![1]) + 1}`, member: member.id, cameraIndex: null}))
            : first.id === 'load_and_track' ? paths.map((_, index) => ({label: `Video ${index + 1}`, member: null, cameraIndex: index})) : [];
        return {
            id, title: group ? group.title : nodeTitle(first.id),
            resource: [...new Set(members.map(member => member.execution_resource))].join(' + '), ...stageOf(first.stage),
            annotation, io, files: paths.map(path => ({name: basename(path), path})), inputs, outputs,
            section: nodeSection(first.id),
            settings: [...new Set(members.flatMap(member => SETTINGS[ANNOTATION.test(member.id) ? 'annotate' : member.id] ?? []))],
            members, lanes,
        };
    });
    return {nodes, edges, nodeOf, kinds};
}

/** A launched processing task: the plan it was admitted with and its operations as the server reports them. */
export interface LaunchedRun {
    taskId: string;
    status: 'queued' | 'running' | 'complete' | 'failed' | 'cancelled';
    plan: ProcessingPlan;
    operations: TaskOperation[];
    /** Per-camera progress the task reports, in camera order. */
    cameras: CameraProgress[];
}

export interface CameraProgress {
    cameraId: string;
    fraction: number | null;
    detail: string;
}

export type OperationState = TaskOperation['status'];

/** Each plan node's operation. Operation ids are plan node ids; an admitted run reports one for every node. */
export function runOperations(run: LaunchedRun): Map<string, TaskOperation> {
    const operations = new Map(run.operations.map(operation => [operation.operation_id, operation]));
    if (run.operations.length === 0) return operations;
    const missing = run.plan.graph.nodes.filter(node => !operations.has(node.id)).map(node => node.id);
    if (missing.length) throw new Error(`Task ${run.taskId} reports no operation for plan node(s): ${missing.join(', ')}`);
    return operations;
}

/** A drawn node's run state: its member operations, one summary of them, and its lanes. */
export interface NodeRun {
    summary: TaskOperation;
    steps: TaskOperation[];
    lanes: {label: string; state: OperationState; fraction: number | null; text: string}[];
}

const sum = (values: (number | null)[]): number | null => values.some(value => value === null) ? null : values.reduce<number>((a, b) => a + b!, 0);

/** Merges member operations without inventing progress: counts are added only when every member reports them. */
export function nodeRun(node: DisplayNode, graph: DisplayGraph, operations: Map<string, TaskOperation>, cameras: CameraProgress[]): NodeRun | null {
    const steps = node.members.map(member => operations.get(member.id)).filter((step): step is TaskOperation => step !== undefined);
    if (steps.length === 0) return null;
    if (steps.length !== node.members.length) throw new Error(`The run reports only some operations of "${node.title}"`);
    const has = (status: OperationState): boolean => steps.some(step => step.status === status);
    const status: OperationState = has('failed') ? 'failed' : has('cancelled') ? 'cancelled' : has('running') ? 'running'
        : steps.every(step => step.status === 'complete') ? 'complete' : has('complete') ? 'running' : 'waiting';
    const parallel = node.lanes.some(lane => lane.member !== null);
    const running = steps.filter(step => step.status === 'running');
    const counted = parallel ? steps : running.length === 1 ? running : status === 'complete' ? [steps[steps.length - 1]] : [];
    const completed = counted.length ? sum(counted.map(step => step.completed)) : null;
    const total = counted.length ? sum(counted.map(step => step.total)) : null;
    const counts = completed !== null && total !== null;
    const elapsed = steps.map(step => step.elapsed_seconds).filter((value): value is number => value !== null);
    const memberIds = new Set(node.members.map(member => member.id));
    const waitingFor = [...new Set(steps.flatMap(step => step.waiting_for ?? []).filter(id => !memberIds.has(id))
        .map(id => graph.nodeOf.get(id) ?? id))];
    const summary: TaskOperation = steps.length === 1 ? {...steps[0], waiting_for: waitingFor} : {
        operation_id: node.id, label: steps.map(step => step.label).join(' · '), status, stage: steps[0].stage,
        progress_fraction: counts && total ? completed / total : running.length === 1 && !parallel ? running[0].progress_fraction : status === 'complete' ? 1 : null,
        completed: counts ? completed : null, total: counts ? total : null, unit: counts ? counted[0].unit : null,
        detail: running.map(step => step.detail).filter(Boolean).join(' · '),
        elapsed_seconds: elapsed.length ? (parallel ? Math.max(...elapsed) : elapsed.reduce((a, b) => a + b, 0)) : null,
        seconds_per_motion_frame: null, waiting_for: waitingFor,
        files_read: [...new Set(steps.flatMap(step => step.files_read ?? []))],
        files_written: [...new Set(steps.flatMap(step => step.files_written ?? []))],
    };
    const lanes = node.lanes.map(lane => {
        if (lane.member !== null) {
            const step = operations.get(lane.member)!;
            return {label: lane.label, state: step.status, fraction: step.status === 'complete' ? 1 : step.progress_fraction,
                text: step.completed !== null && step.total !== null ? `${step.completed}/${step.total}` : ''};
        }
        const camera = cameras[lane.cameraIndex!];
        if (!camera) return {label: lane.label, state: summary.status, fraction: summary.status === 'complete' ? 1 : null, text: ''};
        return {label: lane.label, state: summary.status, fraction: summary.status === 'complete' ? 1 : camera.fraction,
            text: camera.fraction === null ? '' : `${Math.round(camera.fraction * 100)}%`};
    });
    return {summary, steps, lanes};
}

/** Counts with their unit when the server reports them; otherwise elapsed time; otherwise nothing. */
export function operationCount(operation: TaskOperation): string {
    if (operation.completed !== null && operation.total !== null) {
        return `${operation.completed}/${operation.total}${operation.unit ? ` ${operation.unit}` : ''}`;
    }
    if (operation.elapsed_seconds !== null) return `${operation.elapsed_seconds.toFixed(1)} s`;
    return '';
}

/** Operations of one processing stage, in the plan's topological order. Stage 0 holds work outside the stages. */
export interface OperationGroup {
    stageNumber: number;
    stageLabel: string;
    rows: {title: string; operation: TaskOperation}[];
}

/** A run's operations in an order fixed at launch: by processing stage, then by the plan's topological order. */
export function operationGroups(plan: ProcessingPlan, operations: TaskOperation[]): OperationGroup[] {
    const planIds = new Set(plan.graph.nodes.map(node => node.id));
    const unplanned = operations.filter(operation => !planIds.has(operation.operation_id)).map(operation => operation.operation_id);
    if (unplanned.length) throw new Error(`Operations not in the task's plan: ${unplanned.join(', ')}`);
    if (operations.length === 0) return [];
    const byId = new Map(operations.map(operation => [operation.operation_id, operation]));
    const stages = new Map(plan.graph.nodes.map(node => [node.id, stageOf(node.stage)]));
    const groups = new Map<number, OperationGroup>();
    for (const id of plan.topological_order) {
        const operation = byId.get(id);
        if (!operation) throw new Error(`The task reports no operation for plan node "${id}"`);
        const stage = stages.get(id)!;
        const group = groups.get(stage.stageNumber) ?? {...stage, rows: []};
        group.rows.push({title: nodeTitle(id), operation});
        groups.set(stage.stageNumber, group);
    }
    const rank = (group: OperationGroup): number => group.stageNumber === 0 ? PROCESSING_STAGES.length + 1 : group.stageNumber;
    return [...groups.values()].sort((a, b) => rank(a) - rank(b));
}
