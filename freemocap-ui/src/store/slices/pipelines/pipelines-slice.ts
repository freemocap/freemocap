import {createSelector, createSlice, PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '../../types';
import {stopAllPipelines, stopPipeline} from './pipelines-thunks';

// ==================== Pipeline Types ====================

export const PipelineType = {
    CALIBRATION: 'calibration',
    MOCAP: 'mocap',
} as const;
export type PipelineType = (typeof PipelineType)[keyof typeof PipelineType];

export const PipelinePhase = {
    SETTING_UP: 'setting_up',
    PROCESSING_VIDEOS: 'processing_videos',
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
};

export const PHASE_LABELS: Record<PipelinePhase, string> = {
    [PipelinePhase.SETTING_UP]: 'Setting Up',
    [PipelinePhase.PROCESSING_VIDEOS]: 'Processing Videos',
    [PipelinePhase.AGGREGATING]: 'Aggregating',
    [PipelinePhase.FINALIZING]: 'Finalizing',
    [PipelinePhase.COMPLETE]: 'Complete',
    [PipelinePhase.FAILED]: 'Failed',
};

export interface PipelineProgress {
    pipelineId: string;
    pipelineType: PipelineType;
    phase: PipelinePhase;
    progress: number; // 0-100
    detail: string;
    recordingName: string;
    recordingPath: string;
    completedAt?: number; // timestamp when completed/failed
}

// ==================== State ====================

interface PipelinesState {
    activePipelines: Record<string, PipelineProgress>;
    dismissedBasePipelineIds: string[];
    showCompleted: boolean;
    filterText: string;
    snackbarVisible: boolean;
}

const initialState: PipelinesState = {
    activePipelines: {},
    dismissedBasePipelineIds: [],
    showCompleted: false,
    filterText: '',
    snackbarVisible: false,
};

// ==================== Slice ====================

function forceBasePipelineFailed(state: PipelinesState, baseId: string, detail: string) {
    const now = Date.now();
    for (const [id, p] of Object.entries(state.activePipelines)) {
        const colonIdx = id.indexOf(':');
        const thisBase = colonIdx !== -1 ? id.slice(0, colonIdx) : id;
        if (thisBase === baseId && p.phase !== PipelinePhase.COMPLETE && p.phase !== PipelinePhase.FAILED) {
            state.activePipelines[id] = {...p, phase: PipelinePhase.FAILED, detail, completedAt: now};
        }
    }
}

function forceAllActiveFailed(state: PipelinesState, detail: string) {
    const now = Date.now();
    for (const [id, p] of Object.entries(state.activePipelines)) {
        if (p.phase !== PipelinePhase.COMPLETE && p.phase !== PipelinePhase.FAILED) {
            state.activePipelines[id] = {...p, phase: PipelinePhase.FAILED, detail, completedAt: now};
        }
    }
}

export const pipelinesSlice = createSlice({
    name: 'pipelines',
    initialState,
    reducers: {
        pipelineProgressUpdated: (state, action: PayloadAction<PipelineProgress>) => {
            const incoming = action.payload;
            const isTerminal = incoming.phase === PipelinePhase.COMPLETE || incoming.phase === PipelinePhase.FAILED;
            // Derive base pipeline ID (everything before the first colon)
            const colonIdx = incoming.pipelineId.indexOf(':');
            const baseId = colonIdx !== -1 ? incoming.pipelineId.slice(0, colonIdx) : incoming.pipelineId;
            // Open snackbar when this base pipeline ID is not yet tracked at all
            const baseIsNew = !Object.keys(state.activePipelines).some(id => {
                const c = id.indexOf(':');
                return (c !== -1 ? id.slice(0, c) : id) === baseId;
            });
            state.activePipelines[incoming.pipelineId] = {
                ...incoming,
                completedAt: isTerminal ? Date.now() : undefined,
            };
            if (baseIsNew) {
                state.snackbarVisible = true;
                state.dismissedBasePipelineIds = state.dismissedBasePipelineIds.filter(id => id !== baseId);
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
            state.snackbarVisible = false;
        },
        pipelineDismissed: (state, action: PayloadAction<string>) => {
            if (!state.dismissedBasePipelineIds.includes(action.payload)) {
                state.dismissedBasePipelineIds.push(action.payload);
            }
        },
        allPipelinesCleared: (state) => {
            state.activePipelines = {};
            state.dismissedBasePipelineIds = [];
            // snackbarVisible intentionally unchanged — panel stays open/closed as-is
        },
    },
    extraReducers: (builder) => {
        // Regardless of whether the server stop succeeded or failed, the user
        // asked to stop — force the UI to a terminal FAILED state so it never
        // gets stuck in an active/running limbo.
        builder
            .addCase(stopPipeline.fulfilled, (state, action) => {
                forceBasePipelineFailed(state, action.payload, 'Stopped by user');
            })
            .addCase(stopPipeline.rejected, (state, action) => {
                const baseId = (action.payload ?? action.meta.arg) as string;
                forceBasePipelineFailed(state, baseId, 'Stop failed — marked stopped');
            })
            .addCase(stopAllPipelines.fulfilled, (state) => {
                forceAllActiveFailed(state, 'Stopped by user');
            })
            .addCase(stopAllPipelines.rejected, (state) => {
                forceAllActiveFailed(state, 'Stop failed — marked stopped');
            });
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

export const selectGroupedPipelines = createSelector(
    [selectActivePipelines, selectShowCompleted, selectFilterText],
    (pipelines, showCompleted, filterText) => {
        const needle = filterText.toLowerCase();
        const groups = new Map<string, PipelineGroup>();

        for (const p of Object.values(pipelines)) {
            const colonIdx = p.pipelineId.indexOf(':');
            const basePipelineId = colonIdx !== -1 ? p.pipelineId.slice(0, colonIdx) : p.pipelineId;

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
            if (colonIdx !== -1) {
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
            group.isActive = allMembers.some((p) => !isTerminalPhase(p));
            group.recordingName = group.aggregator?.recordingName || group.videoNodes[0]?.recordingName || '';
            group.recordingPath = group.aggregator?.recordingPath || group.videoNodes[0]?.recordingPath || '';
            group.pipelineType = group.aggregator?.pipelineType ?? group.videoNodes[0]?.pipelineType ?? null;

            if (!group.isActive && !showCompleted) continue;

            if (needle) {
                const match =
                    group.basePipelineId.toLowerCase().includes(needle) ||
                    allMembers.some(
                        (p) =>
                            p.detail.toLowerCase().includes(needle) ||
                            p.pipelineId.toLowerCase().includes(needle)
                    );
                if (!match) continue;
            }

            group.videoNodes.sort((a, b) => a.pipelineId.localeCompare(b.pipelineId));
            result.push(group);
        }

        return result.sort((a, b) => {
            if (a.isActive !== b.isActive) return a.isActive ? -1 : 1;
            return a.basePipelineId.localeCompare(b.basePipelineId);
        });
    }
);

export const selectGroupedPipelinesAll = createSelector(
    [selectActivePipelines],
    (pipelines) => {
        const groups = new Map<string, PipelineGroup>();

        for (const p of Object.values(pipelines)) {
            const colonIdx = p.pipelineId.indexOf(':');
            const basePipelineId = colonIdx !== -1 ? p.pipelineId.slice(0, colonIdx) : p.pipelineId;

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
            if (colonIdx !== -1) {
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
            group.isActive = allMembers.some((p) => !isTerminalPhase(p));
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

export const selectActiveBasePipelineCount = createSelector(
    [selectActivePipelines],
    (pipelines) => {
        const activeBaseIds = new Set<string>();
        for (const p of Object.values(pipelines)) {
            const isTerminal = p.phase === PipelinePhase.COMPLETE || p.phase === PipelinePhase.FAILED;
            if (!isTerminal) {
                const colonIdx = p.pipelineId.indexOf(':');
                activeBaseIds.add(colonIdx !== -1 ? p.pipelineId.slice(0, colonIdx) : p.pipelineId);
            }
        }
        return activeBaseIds.size;
    }
);

// ==================== Actions Export ====================

export const selectSnackbarVisible = (state: RootState) => state.pipelines.snackbarVisible;
export const selectDismissedBasePipelineIds = (state: RootState) => state.pipelines.dismissedBasePipelineIds;

export const {pipelineProgressUpdated, toggleShowCompleted, filterTextChanged, pipelineSnackbarShown, pipelineSnackbarHidden, pipelineDismissed, allPipelinesCleared} = pipelinesSlice.actions;

export default pipelinesSlice.reducer;
