import {createAsyncThunk} from "@reduxjs/toolkit";
import {
    selectCameraById,
    selectConfigsForSelectedCameras,
    setError,
    setLoading, updateCameraConfig, updateCameraConfigs
} from "@/store/slices/cameras-slices/camerasSlice";
import { CameraConfig } from "../slices/cameras-slices/camera-types";
import {urlService} from "@/services/urlService";

export const updateCameraConfigsThunk = createAsyncThunk(
    'camera/update',
    async (_, { dispatch, getState }) => {
        const state = getState() as any;
        dispatch(setLoading(true));
        const connectUrl = urlService.getSkellycamUrls().updateCameraConfigs

        const payload = {
            camera_configs: selectConfigsForSelectedCameras(state)
        };

        const requestBody = JSON.stringify(payload, null, 2);
        try {
            console.log(`Updating Camera Configs at ${connectUrl} with request body keys:`, Object.keys(payload));
            const response = await fetch(connectUrl, {
                method: 'PUT',
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
            // Convert the response data to a Record<string, CameraConfig>
            dispatch(updateCameraConfigs(data.camera_configs as Record<string, CameraConfig>));
            dispatch(setError(null));
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
