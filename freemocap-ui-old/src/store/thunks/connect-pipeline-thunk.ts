import {createAsyncThunk} from "@reduxjs/toolkit";
import {selectConfigsForSelectedCameras, setError, setLoading} from "@/store/slices/cameras-slices/camerasSlice";
import {urlService} from "@/config/appUrlService";

export const connectPipelineThunk = createAsyncThunk(
    'pipeline/connect',
    async (_, { dispatch, getState }) : Promise<string> => {
        const state = getState() as any;
        const cameraConfigs = selectConfigsForSelectedCameras(state);

        if (!cameraConfigs || Object.keys(cameraConfigs).length === 0) {
            const errorMsg = 'No camera configurations available to connect the pipeline.';
            console.error(errorMsg);
            dispatch(setError(errorMsg));
            return Promise.reject(new Error(errorMsg));
        }

        const cameraIds = Object.keys(cameraConfigs || {});

        dispatch(setLoading(true));
        const connectUrl = urlService.getHttpEndpointUrls().connectPipeline;

        const payload = {
            camera_ids: cameraIds,
        };

        const requestBody = JSON.stringify(payload, null, 2);
        try {
            console.log(`Connecting to pipeline at ${connectUrl} with body:`, requestBody);
            const response = await fetch(connectUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: requestBody
            });

            const data = await response.json();

            if (!response.ok) {
                let errorMsg = 'Failed to connect to pipeline.';
                if (data.detail) {
                    errorMsg += ` Details: ${JSON.stringify(data.detail)}`;
                }
                console.error('Error:', errorMsg);
                dispatch(setError(errorMsg));
                throw new Error(errorMsg);
            }

            dispatch(setError(null));
            console.log(`Connected to pipeline successfully: ${JSON.stringify(data, null, 2)}`);
            return data.pipeline_id as string;
        } catch (error) {
            const errorMessage = error instanceof Error
                ? `Failed to connect to pipeline: ${error.message}`
                : 'Failed to connect to pipeline: Unknown error';

            dispatch(setError(errorMessage));
            console.error(errorMessage, error);
            throw error;
        } finally {
            dispatch(setLoading(false));
        }
    }
);

export const disconnectPipelineThunk = createAsyncThunk(
    'pipeline/disconnect',
    async (_, { dispatch}) : Promise<void> => {
        dispatch(setLoading(true));
        const disconnectUrl = urlService.getHttpEndpointUrls().disconnectPipeline;

        try {
            console.log(`Sending disconnect request to ${disconnectUrl}`);
            const response = await fetch(disconnectUrl, {method: 'GET'});

            const data = await response.json();

            if (!response.ok) {
                let errorMsg = 'Failed to disconnect from pipeline.';
                if (data.detail) {
                    errorMsg += ` Details: ${JSON.stringify(data.detail)}`;
                }
                console.error('Error:', errorMsg);
                dispatch(setError(errorMsg));
                throw new Error(errorMsg);
            }

            dispatch(setError(null));
            console.log(`Disconnected from pipeline successfully: ${JSON.stringify(data, null, 2)}`);
        } catch (error) {
            const errorMessage = error instanceof Error
                ? `Failed to disconnect from pipeline: ${error.message}`
                : 'Failed to disconnect from pipeline: Unknown error';

            dispatch(setError(errorMessage));
            console.error(errorMessage, error);
            throw error;
        } finally {
            dispatch(setLoading(false));
        }
    }
);
