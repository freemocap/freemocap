import {createAsyncThunk} from "@reduxjs/toolkit";
import {RootState, selectSelectedCameraConfigs} from "@/store";
import {serverUrls} from "@/services";
import {
    PipelineConnectResponse,
    PipelineConnectRequest,
} from "@/store/slices/pipeline/pipeline-types";

export const connectPipeline = createAsyncThunk<
    PipelineConnectResponse,
    PipelineConnectRequest | undefined,
    { state: RootState }>(
    'pipeline/connect',
    async (request={}, {getState}) => {
        const state = getState();

        const cameraConfigs = selectSelectedCameraConfigs(state);
        const response = await fetch(serverUrls.endpoints.pipelineConnectOrUpdate, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ camera_configs: cameraConfigs, ...request }),
        });

        if (!response.ok) {
            const error = await response.json()
            throw new Error(`Failed to connect pipeline: ${error.message || response.statusText}`);
        }
        return response.json() as Promise<PipelineConnectResponse>;
    })


export const closePipeline = createAsyncThunk<void, void, { state: RootState }>(
    'pipeline/close',
    async () => {
        const response = await fetch(serverUrls.endpoints.pipelineClose, {
            method: 'DELETE',
        });

        if (!response.ok) {
            console.error(`Failed to close pipeline: ${response.statusText}`);
        }
    }
);




export const pauseUnpausePipeline = createAsyncThunk<void, void, { state: RootState }>(
    'cameras/pause',
    async () => {
        const response = await fetch(serverUrls.endpoints.pipelinePauseUnpause, {
            method: 'GET',
        });

        if (!response.ok) {
            throw new Error(`Failed to pause/unpause cameras: ${response.statusText}`);
        }
    }
);
