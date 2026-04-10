import {createAsyncThunk, createSelector} from "@reduxjs/toolkit";
import {RootState, selectSelectedCameraConfigs} from "@/store";
import {serverUrls} from "@/services";
import {PipelineApplyResponse, RealtimePipelineConfig} from "@/store/slices/realtime/realtime-types";

export const applyRealtimePipeline = createAsyncThunk<
    PipelineApplyResponse,
    RealtimePipelineConfig,
    { state: RootState }
>(
    'realtime/apply',
    async (realtimeConfig, {getState}) => {
        const cameraConfigs = selectSelectedCameraConfigs(getState());


        const response = await fetch(serverUrls.endpoints.realtimeConnectOrUpdate, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                realtimeConfig,
                cameraConfigs
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(`Failed to apply realtime: ${error.detail || response.statusText}`);
        }

        return response.json() as Promise<PipelineApplyResponse>;
    }
);

export const closePipeline = createAsyncThunk<void, void, { state: RootState }>(
    'realtime/close',
    async () => {
        const response = await fetch(serverUrls.endpoints.realtimeClose, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`Failed to close realtime: ${response.statusText}`);
        }
    }
);
