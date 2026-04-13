import {createSlice, PayloadAction} from '@reduxjs/toolkit';
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
}

// ==================== State ====================

interface PipelinesState {
    activePipelines: Record<string, PipelineProgress>;
}

const initialState: PipelinesState = {
    activePipelines: {},
};

// ==================== Slice ====================

export const pipelinesSlice = createSlice({
    name: 'pipelines',
    initialState,
    reducers: {
        pipelineProgressUpdated: (state, action: PayloadAction<PipelineProgress>) => {
            state.activePipelines[action.payload.pipelineId] = action.payload;
        },
        pipelineRemoved: (state, action: PayloadAction<string>) => {
            delete state.activePipelines[action.payload];
        },
    },
});

// ==================== Selectors ====================

export const selectActivePipelines = (state: RootState) => state.pipelines.activePipelines;

// ==================== Actions Export ====================

export const {pipelineProgressUpdated, pipelineRemoved} = pipelinesSlice.actions;

export default pipelinesSlice.reducer;
