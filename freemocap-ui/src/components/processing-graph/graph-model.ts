import type {ProcessingPlan} from '@/services/recording/processing-plan';
import type {TaskOperation} from '@/services/server/transport/message-contract';
import {PROCESSING_STAGES} from '@/services/recording/posthoc-processing';

/** Plain names for plan nodes, used where single operations are listed (the progress panel). */
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


export const ANNOTATION = /^annotate_camera_(\d+)$/;

export function nodeTitle(id: string): string {
    const annotation = ANNOTATION.exec(id);
    if (annotation) return `Annotate video ${Number(annotation[1]) + 1}`;
    const title = TITLES[id];
    if (!title) throw new Error(`The graph view has no title for plan node "${id}"`);
    return title;
}


/** A plan stage key as its 1-based panel number and label; null is work outside the stages. */
export function stageOf(stage: string | null): {stageNumber: number; stageLabel: string} {
    if (stage === null) return {stageNumber: 0, stageLabel: ''};
    const index = PROCESSING_STAGES.findIndex(([key]) => key === stage);
    if (index < 0) throw new Error(`Unknown processing stage "${stage}"`);
    return {stageNumber: index + 1, stageLabel: PROCESSING_STAGES[index][1]};
}

export const basename = (path: string): string => path.split(/[\\/]/).filter(Boolean).pop() ?? path;

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
