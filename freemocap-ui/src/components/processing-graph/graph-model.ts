import type {ProcessingPlan} from '@/services/recording/processing-plan';
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

/** A plan node as drawn: a card with typed slots, and a disk card when it loads or saves. */
export interface DisplayNode {
    id: string;
    title: string;
    resource: string;
    stageNumber: number;
    stageLabel: string;
    camera: number | null;
    annotation: boolean;
    /** Saves win over loads: a node that reads and writes the recording file is a save. */
    io: 'read' | 'write' | null;
    files: DiskFile[];
    inputs: DisplaySlot[];
    outputs: DisplaySlot[];
    section: SettingsSectionName;
    settings: string[];
    definition: PlanNode;
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

const basename = (path: string): string => path.split(/[\\/]/).filter(Boolean).pop() ?? path;

/** The plan as drawn. Disk cards come only from declared effects and the plan's read paths. */
export function displayGraph(plan: ProcessingPlan): DisplayGraph {
    const kinds: string[] = [];
    const note = (kind: string): void => {
        if (!kinds.includes(kind)) kinds.push(kind);
    };
    const nodeKinds = new Map(plan.graph.nodes.map(node => [node.id, node]));
    const edges: DisplayEdge[] = plan.graph.edges.map(edge => {
        const source = nodeKinds.get(edge.source.node);
        if (!source) throw new Error(`Plan edge from unknown node "${edge.source.node}"`);
        const port = source.outputs.find(output => output.name === edge.source.port);
        if (!port) throw new Error(`Plan edge from unknown slot "${edge.source.node}.${edge.source.port}"`);
        return {id: `${edge.source.node}.${edge.source.port}>${edge.target.node}.${edge.target.port}`,
            source: edge.source.node, sourceSlot: edge.source.port, target: edge.target.node, targetSlot: edge.target.port,
            kind: port.contract.kind, annotation: ANNOTATION.test(edge.target.node)};
    });
    const nodes = plan.graph.nodes.map((node): DisplayNode => {
        const annotation = ANNOTATION.exec(node.id);
        const io = node.effects.includes('write_disk') ? 'write' : node.effects.includes('read_record') || node.effects.includes('read_live') ? 'read' : null;
        const paths = plan.read_paths[node.id] ?? [];
        node.inputs.forEach(port => note(port.contract.kind));
        node.outputs.forEach(port => note(port.contract.kind));
        return {
            id: node.id, title: nodeTitle(node.id), resource: node.execution_resource, ...stageOf(node.stage),
            camera: annotation ? Number(annotation[1]) : null, annotation: Boolean(annotation), io,
            files: paths.map(path => ({name: basename(path), path})),
            inputs: node.inputs.map(port => ({name: port.name, kind: port.contract.kind,
                from: edges.find(edge => edge.target === node.id && edge.targetSlot === port.name)?.source ?? null})),
            outputs: node.outputs.map(port => ({name: port.name, kind: port.contract.kind, from: null})),
            section: nodeSection(node.id), settings: SETTINGS[annotation ? 'annotate' : node.id] ?? [], definition: node,
        };
    });
    return {nodes, edges, kinds};
}
