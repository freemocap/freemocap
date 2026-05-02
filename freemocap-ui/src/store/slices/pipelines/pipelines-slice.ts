import {createSelector, createSlice, PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '../../types';

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
    completedAt?: number; // timestamp when completed/failed
}

// ==================== State ====================

interface PipelinesState {
    activePipelines: Record<string, PipelineProgress>;
    showCompleted: boolean;
    filterText: string;
}

const initialState: PipelinesState = {
    activePipelines: {},
    showCompleted: false,
    filterText: '',
};

// ==================== Slice ====================

export const pipelinesSlice = createSlice({
    name: 'pipelines',
    initialState,
    reducers: {
        pipelineProgressUpdated: (state, action: PayloadAction<PipelineProgress>) => {
            const incoming = action.payload;
            const isTerminal = incoming.phase === PipelinePhase.COMPLETE || incoming.phase === PipelinePhase.FAILED;
            state.activePipelines[incoming.pipelineId] = {
                ...incoming,
                completedAt: isTerminal ? Date.now() : undefined,
            };
        },
        toggleShowCompleted: (state) => {
            state.showCompleted = !state.showCompleted;
        },
        filterTextChanged: (state, action: PayloadAction<string>) => {
            state.filterText = action.payload;
        },
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
    videoNodes: PipelineProgress[];
    aggregator: PipelineProgress | null;
    isActive: boolean;
    isFailed: boolean;
    isComplete: boolean;
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
                    videoNodes: [],
                    aggregator: null,
                    isActive: false,
                    isFailed: false,
                    isComplete: false,
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

export const {pipelineProgressUpdated, toggleShowCompleted, filterTextChanged} = pipelinesSlice.actions;

export default pipelinesSlice.reducer;
