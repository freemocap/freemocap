import {createSelector, createSlice, PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '../../root-state-types';
import {stopAllPipelines, stopPipeline} from './pipelines-thunks';
import type {TaskRegistrySnapshot} from '@/services/server/transport/message-contract';
import {loadFromStorage} from '@/store/persistence';

export function phaseForTask(phase: string): PipelinePhase {
    const phases: Record<string, PipelinePhase> = {
        queued: PipelinePhase.QUEUED, setting_up: PipelinePhase.SETTING_UP,
        processing_images: PipelinePhase.PROCESSING_VIDEOS, collecting_camera_output: PipelinePhase.COLLECTING,
        building_recorders: PipelinePhase.AGGREGATING, triangulating: PipelinePhase.AGGREGATING,
        filtering: PipelinePhase.AGGREGATING, reconstructing: PipelinePhase.AGGREGATING,
        exporting_blender: PipelinePhase.FINALIZING, validating_observations: PipelinePhase.SOLVING,
        running_solver: PipelinePhase.SOLVING, saving_calibration: PipelinePhase.SAVING,
        complete: PipelinePhase.COMPLETE, failed: PipelinePhase.FAILED,
    };
    const value = phases[phase];
    if (!value) throw new Error(`Unknown task phase: ${phase}`);
    return value;
}

// ==================== Pipeline Types ====================

export const PipelineType = {
    CALIBRATION: 'calibration',
    MOCAP: 'mocap',
    SYNC: 'sync',
} as const;
export type PipelineType = (typeof PipelineType)[keyof typeof PipelineType];

export const PipelinePhase = {
    QUEUED: 'queued',
    SETTING_UP: 'setting_up',
    PROCESSING_VIDEOS: 'processing_videos',
    COLLECTING: 'collecting_camera_output',
    SOLVING: 'running_solver',
    SAVING: 'saving_calibration',
    AGGREGATING: 'aggregating',
    FINALIZING: 'finalizing',
    COMPLETE: 'complete',
    FAILED: 'failed',
} as const;
export type PipelinePhase = (typeof PipelinePhase)[keyof typeof PipelinePhase];

export interface PipelineTypeConfig {
    label: string;
    color: string;
}

export const PIPELINE_TYPE_CONFIG: Record<PipelineType, PipelineTypeConfig> = {
    [PipelineType.CALIBRATION]: {label: 'Calibration', color: '#26C6DA'},
    [PipelineType.MOCAP]:       {label: 'Mocap',        color: '#AB47BC'},
    [PipelineType.SYNC]:        {label: 'Synchronize',  color: '#66BB6A'},
};

export const PHASE_LABELS: Record<PipelinePhase, string> = {
    [PipelinePhase.QUEUED]: 'Queued',
    [PipelinePhase.SETTING_UP]: 'Setting Up',
    [PipelinePhase.PROCESSING_VIDEOS]: 'Processing Videos',
    [PipelinePhase.COLLECTING]: 'Collect observations',
    [PipelinePhase.SOLVING]: 'Calibrate cameras',
    [PipelinePhase.SAVING]: 'Save results',
    [PipelinePhase.AGGREGATING]: 'Aggregating',
    [PipelinePhase.FINALIZING]: 'Finalizing',
    [PipelinePhase.COMPLETE]: 'Complete',
    [PipelinePhase.FAILED]: 'Failed',
};

export const CALIBRATION_STAGES: readonly PipelinePhase[] = [
    PipelinePhase.COLLECTING, PipelinePhase.SOLVING, PipelinePhase.SAVING,
];

export interface PipelineProgress {
    basePipelineId: string;
    cameraId: string | null;
    pipelineId: string;
    pipelineType: PipelineType;
    phase: PipelinePhase;
    progress: number | null; // 0-100; null means unmeasured
    detail: string;
    recordingName: string;
    recordingPath: string;
    calibrationStage?: PipelinePhase;
    completedAt?: number; // timestamp when completed/failed
}

// ==================== State ====================

interface PipelinesState {
    recordingOwners: TaskRegistrySnapshot['recording_owners'];
    serverInstanceId: string | null;
    registryRevision: number;
    cancellationError: string | null;
    activePipelines: Record<string, PipelineProgress>;
    dismissedBasePipelineIds: string[];
    showCompleted: boolean;
    filterText: string;
    snackbarVisible: boolean;
}

const dismissedTasks = loadFromStorage<{serverInstanceId: string | null; dismissedBasePipelineIds: string[]}>(
    'pipelines.dismissals', {serverInstanceId: null, dismissedBasePipelineIds: []});

const initialState: PipelinesState = {
    recordingOwners: [],
    serverInstanceId: dismissedTasks.serverInstanceId,
    registryRevision: -1,
    cancellationError: null,
    activePipelines: {},
    dismissedBasePipelineIds: dismissedTasks.dismissedBasePipelineIds,
    showCompleted: false,
    filterText: '',
    snackbarVisible: false,
};

// ==================== Slice ====================

function dismissCompletedTasks(state: PipelinesState): void {
    state.dismissedBasePipelineIds = [...new Set([
        ...state.dismissedBasePipelineIds,
        ...Object.values(state.activePipelines)
            .filter(pipeline => pipeline.cameraId === null && pipeline.completedAt !== undefined)
            .map(pipeline => pipeline.basePipelineId),
    ])];
}

export const pipelinesSlice = createSlice({
    name: 'pipelines',
    initialState,
    reducers: {
        taskSnapshotReceived: (state, action: PayloadAction<TaskRegistrySnapshot>) => {
            const snapshot = action.payload;
            if (state.serverInstanceId === snapshot.server_instance_id && snapshot.revision <= state.registryRevision) return;
            const sameServer = state.serverInstanceId === snapshot.server_instance_id;
            const previous = sameServer ? state.activePipelines : {};
            state.serverInstanceId = snapshot.server_instance_id;
            state.registryRevision = snapshot.revision;
            state.recordingOwners = snapshot.recording_owners;
            if (!sameServer) state.dismissedBasePipelineIds = [];
            const newTaskStarted = snapshot.tasks.some(task => task.status === 'running' && !previous[task.task_id]);
            if (newTaskStarted) {
                state.dismissedBasePipelineIds = [...new Set([
                    ...state.dismissedBasePipelineIds,
                    ...snapshot.tasks.filter(task => task.status !== 'running').map(task => task.task_id),
                ])];
            }
            state.activePipelines = {};
            for (const task of snapshot.tasks) {
                const common = {pipelineType: task.task_type, recordingName: task.recording.recording_name,
                    recordingPath: task.recording.full_path, basePipelineId: task.task_id};
                const phase = phaseForTask(task.progress.phase);
                const terminal = task.status !== 'running';
                state.activePipelines[task.task_id] = {...common, pipelineId: task.task_id, cameraId: null,
                    phase, progress: task.progress.progress_fraction === null ? null : Math.round(task.progress.progress_fraction * 100),
                    detail: task.progress.detail, completedAt: terminal ? Date.parse(task.updated_at) : undefined,
                    calibrationStage: CALIBRATION_STAGES.includes(phase) ? phase : undefined};
                for (const camera of task.cameras) {
                    state.activePipelines[camera.node_id] = {...common, pipelineId: camera.node_id, cameraId: camera.camera_id,
                        phase: phaseForTask(camera.progress.phase),
                        progress: camera.progress.progress_fraction === null ? null : Math.round(camera.progress.progress_fraction * 100),
                        detail: camera.progress.detail};
                }
                if (!previous[task.task_id] && !terminal) state.snackbarVisible = true;
            }
        },
        toggleShowCompleted: (state) => {
            state.showCompleted = !state.showCompleted;
        },
        filterTextChanged: (state, action: PayloadAction<string>) => {
            state.filterText = action.payload;
        },
        pipelineSnackbarShown: (state) => {
            state.snackbarVisible = true;
        },
        pipelineSnackbarHidden: (state) => {
            dismissCompletedTasks(state);
            state.snackbarVisible = false;
        },
        pipelineDismissed: (state, action: PayloadAction<string>) => {
            if (!state.dismissedBasePipelineIds.includes(action.payload)) {
                state.dismissedBasePipelineIds.push(action.payload);
            }
        },
        allPipelinesCleared: (state) => {
            dismissCompletedTasks(state);
            // snackbarVisible intentionally unchanged — panel stays open/closed as-is
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(stopPipeline.pending, (state) => {
                state.cancellationError = null;
            })

            .addCase(stopPipeline.rejected, (state, action) => {
                state.cancellationError = action.error.message ?? 'Pipeline cancellation failed';
            })
            .addCase(stopAllPipelines.rejected, (state, action) => {
                state.cancellationError = action.error.message ?? 'Some pipelines could not be cancelled';
            })
            ;
    },
});

// ==================== Selectors ====================

export const selectActivePipelines = (state: RootState) => state.pipelines.activePipelines;
export const selectShowCompleted = (state: RootState) => state.pipelines.showCompleted;
export const selectFilterText = (state: RootState) => state.pipelines.filterText;

export const selectFilteredPipelines = createSelector(
    [selectActivePipelines, selectShowCompleted, selectFilterText],
    (pipelines, showCompleted, filterText) => {
        const entries = Object.values(pipelines);
        const needle = filterText.toLowerCase();

        return entries
            .filter((p) => {
                const isTerminal = p.phase === PipelinePhase.COMPLETE || p.phase === PipelinePhase.FAILED;
                if (isTerminal && !showCompleted) return false;
                if (needle) {
                    return (
                        p.pipelineId.toLowerCase().includes(needle) ||
                        p.pipelineType.toLowerCase().includes(needle) ||
                        p.detail.toLowerCase().includes(needle)
                    );
                }
                return true;
            })
            .sort((a, b) => {
                const aTerminal = a.completedAt != null;
                const bTerminal = b.completedAt != null;
                if (aTerminal !== bTerminal) return aTerminal ? 1 : -1;
                if (aTerminal && bTerminal) return (b.completedAt! - a.completedAt!);
                return 0;
            });
    }
);

export const selectHasCompletedPipelines = createSelector(
    [selectActivePipelines],
    (pipelines) => Object.values(pipelines).some(
        (p) => p.phase === PipelinePhase.COMPLETE || p.phase === PipelinePhase.FAILED
    )
);

// ==================== Grouped Pipeline Selectors ====================

export interface PipelineGroup {
    basePipelineId: string;
    pipelineType: PipelineType | null;
    videoNodes: PipelineProgress[];
    aggregator: PipelineProgress | null;
    isActive: boolean;
    isFailed: boolean;
    isComplete: boolean;
    recordingName: string;
    recordingPath: string;
}

// Shared base: groups all pipelines into PipelineGroup objects without filtering.
// Both selectGroupedPipelines and selectGroupedPipelinesAll derive from this
// so grouping + flag computation runs only once per pipeline state change.
const selectAllGroupsUnfiltered = createSelector(
    [selectActivePipelines],
    (pipelines) => {
        const groups = new Map<string, PipelineGroup>();

        for (const p of Object.values(pipelines)) {
            const basePipelineId = p.basePipelineId;


            if (!groups.has(basePipelineId)) {
                groups.set(basePipelineId, {
                    basePipelineId,
                    pipelineType: null,
                    videoNodes: [],
                    aggregator: null,
                    isActive: false,
                    isFailed: false,
                    isComplete: false,
                    recordingName: '',
                    recordingPath: '',
                });
            }
            const group = groups.get(basePipelineId)!;
            if (p.cameraId !== null) {
                group.videoNodes.push(p);
            } else {
                group.aggregator = p;
            }
        }

        const isTerminalPhase = (p: PipelineProgress) =>
            p.phase === PipelinePhase.COMPLETE || p.phase === PipelinePhase.FAILED;

        const result: PipelineGroup[] = [];
        for (const group of groups.values()) {
            const allMembers = [...group.videoNodes, ...(group.aggregator ? [group.aggregator] : [])];

            group.isFailed = allMembers.some((p) => p.phase === PipelinePhase.FAILED);
            group.isComplete = !!group.aggregator && group.aggregator.phase === PipelinePhase.COMPLETE;
            group.isActive = !group.isFailed && !group.isComplete && allMembers.some((p) => !isTerminalPhase(p));
            group.recordingName = group.aggregator?.recordingName || group.videoNodes[0]?.recordingName || '';
            group.recordingPath = group.aggregator?.recordingPath || group.videoNodes[0]?.recordingPath || '';
            group.pipelineType = group.aggregator?.pipelineType ?? group.videoNodes[0]?.pipelineType ?? null;

            group.videoNodes.sort((a, b) => a.pipelineId.localeCompare(b.pipelineId));
            result.push(group);
        }

        return result.sort((a, b) => {
            if (a.isActive !== b.isActive) return a.isActive ? -1 : 1;
            return a.basePipelineId.localeCompare(b.basePipelineId);
        });
    }
);

export const selectGroupedPipelines = createSelector(
    [selectAllGroupsUnfiltered, selectShowCompleted, selectFilterText],
    (allGroups, showCompleted, filterText) => {
        const needle = filterText.toLowerCase();

        return allGroups.filter(group => {
            if (!group.isActive && !showCompleted) return false;

            if (needle) {
                const allMembers = [...group.videoNodes, ...(group.aggregator ? [group.aggregator] : [])];
                const match =
                    group.basePipelineId.toLowerCase().includes(needle) ||
                    allMembers.some(
                        (p) =>
                            p.detail.toLowerCase().includes(needle) ||
                            p.pipelineId.toLowerCase().includes(needle)
                    );
                if (!match) return false;
            }

            return true;
        });
    }
);

export const selectGroupedPipelinesAll = selectAllGroupsUnfiltered;

export const selectActiveBasePipelineCount = createSelector(
    [selectActivePipelines],
    (pipelines) => {
        const activeBaseIds = new Set<string>();
        for (const p of Object.values(pipelines)) {
            const isTerminal = p.phase === PipelinePhase.COMPLETE || p.phase === PipelinePhase.FAILED;
            if (!isTerminal) {
                const basePipelineId = p.basePipelineId;
                activeBaseIds.add(basePipelineId);
            }
        }
        return activeBaseIds.size;
    }
);

// ==================== Actions Export ====================

export const selectSnackbarVisible = (state: RootState) => state.pipelines.snackbarVisible;
export const selectDismissedBasePipelineIds = (state: RootState) => state.pipelines.dismissedBasePipelineIds;

export const {taskSnapshotReceived, toggleShowCompleted, filterTextChanged, pipelineSnackbarShown, pipelineSnackbarHidden, pipelineDismissed, allPipelinesCleared} = pipelinesSlice.actions;

export default pipelinesSlice.reducer;

