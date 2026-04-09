import {createSlice} from "@reduxjs/toolkit";
import {PipelineState} from "@/store/slices/realtime/realtime-types";
import {closePipeline, connectRealtimePipeline} from "@/store/slices/realtime/realtime-thunks";
import {serverSettingsCleared, serverSettingsUpdated} from "@/store/slices/settings/settings-slice";

const initialState: PipelineState = {
    cameraGroupId: null,
    pipelineId: null,
    isConnected: false,
    isLoading: false,
    error: null,
}

export const realtimeSlice = createSlice({
    name: 'pipeline',
    initialState,
    reducers: {
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
            // ========== Connect Pipeline (HTTP) ==========
            .addCase(connectRealtimePipeline.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(connectRealtimePipeline.fulfilled, (state, action) => {
                state.cameraGroupId = action.payload.camera_group_id;
                state.pipelineId = action.payload.pipeline_id;
                state.isConnected = true;
                state.isLoading = false;
            })
            .addCase(connectRealtimePipeline.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to connect pipeline';
            })

            // ========== Close Pipeline (HTTP) ==========
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
                state.error = action.error.message || 'Failed to disconnect pipeline';
            })

            // ========== WebSocket settings/state — sync pipeline status ==========
            .addCase(serverSettingsUpdated, (state, action) => {
                const backendPipeline = action.payload.settings.pipeline;
                // Only overwrite if not mid-HTTP-request (isLoading guards against races)
                if (!state.isLoading) {
                    state.isConnected = backendPipeline.is_connected;
                    state.pipelineId = backendPipeline.pipeline_id;
                    state.cameraGroupId = backendPipeline.camera_group_id;
                }
            })

            // ========== WebSocket disconnected — clear pipeline state ==========
            .addCase(serverSettingsCleared, (state) => {
                state.cameraGroupId = null;
                state.pipelineId = null;
                state.isConnected = false;
                state.isLoading = false;
                state.error = null;
            });
    },
});

export const {pipelineStateReset} = realtimeSlice.actions;
