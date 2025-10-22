import {createAsyncThunk} from "@reduxjs/toolkit";
import {RootState} from "@/store";
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

        // if no camera IDs provided, use all selected cameras
        const cameraIds = request.camera_ids || state.cameras.cameras
            .filter(cam => cam.selected)
            .map(cam => cam.id);

        const response = await fetch(serverUrls.endpoints.pipelineConnect, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ camera_ids: cameraIds }),
        });

        if (!response.ok) {
            const error = await response.json()
            throw new Error(`Failed to connect pipeline: ${error.message || response.statusText}`);
        }
        return response.json() as Promise<PipelineConnectResponse>;
    })


export const disconnectPipeline = createAsyncThunk<void, void, { state: RootState }>(
    'pipeline/disconnect',
    async () => {
        const response = await fetch(serverUrls.endpoints.pipelineDisconnect, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`Failed to disconnect pipeline: ${response.statusText}`);
        }
    }
);
