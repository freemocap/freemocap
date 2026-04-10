import {createSlice, PayloadAction} from "@reduxjs/toolkit";
import {defaultRealtimePipelineConfig, PipelineState, RealtimePipelineConfig} from "@/store/slices/realtime/realtime-types";
import {applyRealtimePipeline, closePipeline} from "@/store/slices/realtime/realtime-thunks";

const initialState: PipelineState = {
    pipelineConfig: defaultRealtimePipelineConfig,
    cameraGroupId: null,
    pipelineId: null,
    isConnected: false,
    isLoading: false,
    error: null,
};

export const realtimeSlice = createSlice({
    name: 'pipeline',
    initialState,
    reducers: {
        pipelineStateReset: () => initialState,

        pipelineConfigUpdated: (state, action: PayloadAction<RealtimePipelineConfig>) => {
            state.pipelineConfig = action.payload;
        },
    },
    extraReducers: (builder) => {
        builder
            // ========== Apply Pipeline (POST /realtime/apply) ==========
            .addCase(applyRealtimePipeline.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(applyRealtimePipeline.fulfilled, (state, action) => {
                state.cameraGroupId = action.payload.camera_group_id;
                state.pipelineId = action.payload.pipeline_id;
                state.pipelineConfig = action.meta.arg;
                state.isConnected = true;
                state.isLoading = false;
            })
            .addCase(applyRealtimePipeline.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to apply pipeline';
            })

            // ========== Close Pipeline (DELETE /realtime/all/close) ==========
            .addCase(closePipeline.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(closePipeline.fulfilled, (state) => {
                state.cameraGroupId = null;
                state.pipelineId = null;
                state.isConnected = false;
                state.isLoading = false;
            })
            .addCase(closePipeline.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to close pipeline';
            });
    },
});

export const {pipelineStateReset, pipelineConfigUpdated} = realtimeSlice.actions;
