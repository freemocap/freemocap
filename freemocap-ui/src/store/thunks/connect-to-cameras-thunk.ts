import {createAsyncThunk} from "@reduxjs/toolkit";
import {
    selectConfigsForSelectedCameras,
    setError,
    setLoading,
    updateCameraConfigs
} from "@/store/slices/cameras-slices/camerasSlice";
import {CameraConfig} from "@/store/slices/cameras-slices/camera-types";
import {urlService} from "@/config/appUrlService";

export const connectToCameras = createAsyncThunk(
    'cameras/connect',
    async (_, { dispatch, getState }) => {
        const state = getState() as any;
        const cameraConfigs = selectConfigsForSelectedCameras(state);

        if (!cameraConfigs || Object.keys(cameraConfigs).length === 0) {
            const errorMsg = 'No camera devices selected for connection';
            dispatch(setError(errorMsg));
            throw new Error(errorMsg);
        }

        dispatch(setLoading(true));
        const connectUrl = urlService.getHttpEndpointUrls().createGroup;

        const payload = {
            camera_configs: cameraConfigs
        };

        const requestBody = JSON.stringify(payload, null, 2);
        try {
            console.log(`Connecting to cameras at ${connectUrl} with body:`, requestBody);
            const response = await fetch(connectUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: requestBody
            });

            // Parse the response body
            const data = await response.json();

            // Check for different error status codes
            if (!response.ok) {
                let errorMsg = 'Failed to connect to cameras';
                console.error('Errors:', data.detail);
                dispatch(setError(errorMsg));
                throw new Error(errorMsg);
            }

            dispatch(setError(null));
            dispatch(updateCameraConfigs(data.camera_configs as Record<string, CameraConfig>));
            return data;
        } catch (error) {
            // Handle network errors and JSON parsing errors
            const errorMessage = error instanceof Error
                ? `Failed to connect to cameras: ${error.message}`
                : 'Failed to connect to cameras: Unknown error';

            dispatch(setError(errorMessage));
            console.error(errorMessage, error);
            throw error;
        } finally {
            dispatch(setLoading(false));
        }
    }
);
