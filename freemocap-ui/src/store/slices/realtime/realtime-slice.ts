import {createSlice, PayloadAction} from "@reduxjs/toolkit";
import {defaultRealtimePipelineConfig, PipelineState, RealtimePipelineConfig} from "@/store/slices/realtime/realtime-types";
import {applyRealtimePipeline, closePipeline, fetchTemporalConfig, applyTemporalConfig} from "@/store/slices/realtime/realtime-thunks";
import {serverStateReceived, serverDisconnected} from "@/store/slices/connection/connection-slice";
import {matchesSavedManualOffset, saveCalibrationTransform} from '@/store/slices/calibration/calibration-save';

const initialState: PipelineState = {
    temporalStatus: null,
    temporalLoading: false,
    temporalError: null,
    pipelineConfig: defaultRealtimePipelineConfig,
    cameraGroupId: null,
    pipelineId: null,
    isConnected: false,
    isLoading: false,
    error: null,
};

export const realtimeSlice = createSlice({
    name: 'realtime',
    initialState,
    reducers: {
        pipelineStateReset: () => initialState,

        pipelineConfigUpdated: (state, action: PayloadAction<RealtimePipelineConfig>) => {
            state.pipelineConfig = action.payload;
        },

        pipelineErrorCleared: (state) => {
            state.error = null;
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchTemporalConfig.fulfilled, (state, action) => {
                state.temporalStatus = action.payload;
                state.temporalError = null;
                const current = state.pipelineConfig.aggregator_config;
                current.realtime_filter_config = action.payload.requested ?? current.realtime_filter_config ?? action.payload.defaults;
            })
            .addCase(fetchTemporalConfig.rejected, (state, action) => {
                state.temporalError = action.error.message ?? 'Could not read filter settings';
            })
            .addCase(applyTemporalConfig.pending, (state) => {
                state.temporalLoading = true;
                state.temporalError = null;
            })
            .addCase(applyTemporalConfig.fulfilled, (state, action) => {
                state.temporalLoading = false;
                state.temporalStatus = action.payload;
                if (action.payload.requested) state.pipelineConfig.aggregator_config.realtime_filter_config = action.payload.requested;
            })
            .addCase(applyTemporalConfig.rejected, (state, action) => {
                state.temporalLoading = false;
                state.temporalError = action.error.message ?? 'Could not apply filter settings';
            });
        builder
            .addCase(saveCalibrationTransform.pending, (state) => {
                state.isLoading = true;
            })
            .addCase(saveCalibrationTransform.fulfilled, (state, action) => {
                state.isLoading = false;
                const config = state.pipelineConfig.aggregator_config;
                if (config.calibration_toml_path === action.payload.path
                    && (!action.meta.arg || matchesSavedManualOffset(
                        action.meta.arg, config.reference_transform?.matrix ?? null,
                    ))) {
                    config.reference_transform = null;
                }
            })
            .addCase(saveCalibrationTransform.rejected, (state) => {
                state.isLoading = false;
            });
        builder
            // ========== Apply Pipeline (POST /realtime/apply) ==========
            .addCase(applyRealtimePipeline.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(applyRealtimePipeline.fulfilled, (state, action) => {
                state.cameraGroupId = action.payload.camera_group_id;
                state.pipelineId = action.payload.pipeline_id;
                state.pipelineConfig = action.payload.resolved_config;
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
            })

            // ========== Server state snapshot (authoritative) ==========
            // Reconcile observed pipeline state from the pushed snapshot. The
            // `!isLoading` guard avoids clobbering an in-flight apply/close.
            .addCase(serverStateReceived, (state, action) => {
                const pipelines = action.payload.state.realtime_pipelines ?? [];
                const alive = pipelines.find(p => p.alive);
                if (alive) {
                    state.isConnected = true;
                    state.pipelineId = alive.id;
                    state.cameraGroupId = alive.camera_group_id;
                } else if (!state.isLoading) {
                    state.isConnected = false;
                    state.pipelineId = null;
                    state.cameraGroupId = null;
                }
            })

            // On websocket disconnect, reset so nothing goes stale.
            .addCase(serverDisconnected, (state) => {
                state.temporalStatus = null;
                state.isConnected = false;
                state.pipelineId = null;
                state.cameraGroupId = null;
            });
    },
});

export const {pipelineStateReset, pipelineConfigUpdated, pipelineErrorCleared} = realtimeSlice.actions;
