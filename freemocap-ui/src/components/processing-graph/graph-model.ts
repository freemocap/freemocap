import type {ProcessingPlan} from '@/services/recording/processing-plan';
import {PROCESSING_STAGES} from '@/services/recording/posthoc-processing';

export type NodeEffect = ProcessingPlan['graph']['nodes'][number]['effects'][number];

/** The settings section that holds a node's configuration, named as in the mocap processing window. */
export type SettingsSectionName = 'Processing stages' | 'Detectors' | 'Camera geometry' | 'Triangulation'
    | 'Post-processing' | 'Exports' | 'Blender';

export interface DisplaySlot {
    name: string;
    /** The data contract kind carried by the slot, or the record/disk/display a terminal stands for. */
    kind: string;
}

/** A computation in the plan, or a terminal: where data enters (source) or ends (sink). */
export interface DisplayNode {
    id: string;
    role: 'operation' | 'source' | 'sink';
    title: string;
    stageLabel: string;
    effect: NodeEffect | null;
    inputs: DisplaySlot[];
    outputs: DisplaySlot[];
    section: SettingsSectionName | null;
    /** Files a source reads, from the plan's read paths. */
    files: string[];
}

export interface DisplayEdge {
    id: string;
    source: string;
    sourceSlot: string;
    target: string;
    targetSlot: string;
}

export interface DisplayGraph {
    nodes: DisplayNode[];
    edges: DisplayEdge[];
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
    spatial_request: 'Processing stages',
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

const ANNOTATION = /^annotate_camera_(\d+)$/;

export function nodeTitle(id: string): string {
    const annotation = ANNOTATION.exec(id);
    if (annotation) return `Draw tracking on video ${Number(annotation[1]) + 1}`;
    const title = TITLES[id];
    if (!title) throw new Error(`The graph view has no title for plan node "${id}"`);
    return title;
}

export function nodeSection(id: string): SettingsSectionName | null {
    if (ANNOTATION.test(id)) return 'Detectors';
    const section = SECTIONS[id];
    if (!section) throw new Error(`The graph view has no settings section for plan node "${id}"`);
    return section;
}

export function stageLabel(stage: string | null): string {
    if (stage === null) return '';
    const entry = PROCESSING_STAGES.find(([key]) => key === stage);
    if (!entry) throw new Error(`Unknown processing stage "${stage}"`);
    return entry[1];
}

const basename = (path: string): string => path.split(/[\\/]/).filter(Boolean).pop() ?? path;

/** A short name for what a source reads: one file by name, several by count and kind. */
export function describeFiles(files: string[]): string {
    if (files.length === 0) return 'Saved recording data';
    if (files.length === 1) return basename(files[0]);
    const extensions = new Set(files.map(file => basename(file).split('.').pop()?.toLowerCase()));
    if (extensions.size === 1 && ['mp4', 'avi', 'mov', 'mkv'].includes([...extensions][0] ?? '')) return `${files.length} videos`;
    return `${files.length} files`;
}

const SINK_TITLES: Record<'write_disk' | 'display', string> = {write_disk: 'Saved to disk', display: 'Opened for display'};

/**
 * The plan as drawn: every operation, plus a source terminal for each record or live read
 * and a sink terminal for each disk write or display. Terminals come only from declared effects.
 */
export function displayGraph(plan: ProcessingPlan): DisplayGraph {
    const nodes: DisplayNode[] = [];
    const edges: DisplayEdge[] = plan.graph.edges.map(edge => ({
        id: `${edge.source.node}.${edge.source.port}->${edge.target.node}.${edge.target.port}`,
        source: edge.source.node, sourceSlot: edge.source.port,
        target: edge.target.node, targetSlot: edge.target.port,
    }));
    for (const node of plan.graph.nodes) {
        const reads = node.effects.filter(effect => effect === 'read_record' || effect === 'read_live');
        const sinks = node.effects.filter((effect): effect is 'write_disk' | 'display' => effect === 'write_disk' || effect === 'display');
        const files = plan.read_paths[node.id] ?? [];
        nodes.push({
            id: node.id, role: 'operation', title: nodeTitle(node.id), stageLabel: stageLabel(node.stage), effect: null,
            inputs: [...node.inputs.map(port => ({name: port.name, kind: port.contract.kind})),
                ...reads.map(effect => ({name: `@${effect}`, kind: effect === 'read_live' ? 'live source' : 'record'}))],
            outputs: [...node.outputs.map(port => ({name: port.name, kind: port.contract.kind})),
                ...sinks.map(effect => ({name: `@${effect}`, kind: effect === 'display' ? 'display' : 'disk'}))],
            section: nodeSection(node.id), files,
        });
        for (const effect of reads) {
            const id = `${effect}:${node.id}`;
            nodes.push({id, role: 'source', title: effect === 'read_live' ? 'Live cameras' : describeFiles(files),
                stageLabel: '', effect, inputs: [], outputs: [{name: 'data', kind: effect === 'read_live' ? 'live source' : 'record'}],
                section: null, files});
            edges.push({id: `${id}->${node.id}`, source: id, sourceSlot: 'data', target: node.id, targetSlot: `@${effect}`});
        }
        for (const effect of sinks) {
            const id = `${effect}:${node.id}`;
            nodes.push({id, role: 'sink', title: SINK_TITLES[effect], stageLabel: '', effect,
                inputs: [{name: 'data', kind: effect === 'display' ? 'display' : 'disk'}], outputs: [], section: null, files: []});
            edges.push({id: `${node.id}->${id}`, source: node.id, sourceSlot: `@${effect}`, target: id, targetSlot: 'data'});
        }
    }
    return {nodes, edges};
}
