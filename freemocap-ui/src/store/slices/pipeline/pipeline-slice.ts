import {createSlice} from "@reduxjs/toolkit";
import {PipelineState} from "@/store/slices/pipeline/pipeline-types";
import {connectPipeline, disconnectPipeline} from "@/store/slices/pipeline/pipeline-thunks";

const initialState: PipelineState = {
    cameraGroupId: null,
    pipelineId: null,
    isConnected: false,
    isLoading: false,
    error: null,
}

export const pipelineSlice = createSlice({
    name: 'pipeline',
    initialState,
    reducers: {
        // Manual state reset
        pipelineStateReset: (state) => {
            state.cameraGroupId = null;
            state.pipelineId = null;
            state.isConnected = false;
            state.isLoading = false;
            state.error = null;
        }
    },
    extraReducers: (builder) => {
        builder
        // Connect Pipeline
            .addCase(connectPipeline.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(connectPipeline.fulfilled, (state, action) => {
                state.cameraGroupId = action.payload.camera_group_id;
                state.pipelineId = action.payload.pipeline_id;
                state.isConnected = true;
                state.isLoading = false;
            })
            .addCase(connectPipeline.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to connect pipeline';
            })

        // disconnect pipeline
         .addCase(disconnectPipeline.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(disconnectPipeline.fulfilled, (state) => {
                state.cameraGroupId = null;
                state.pipelineId = null;
                state.isConnected = false;
                state.isLoading = false;
            })
            .addCase(disconnectPipeline.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to disconnect pipeline';
            });
    },
});

export const {pipelineStateReset} = pipelineSlice.actions;
