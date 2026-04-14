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

// ==================== Actions Export ====================

export const {pipelineProgressUpdated, toggleShowCompleted, filterTextChanged} = pipelinesSlice.actions;

export default pipelinesSlice.reducer;
