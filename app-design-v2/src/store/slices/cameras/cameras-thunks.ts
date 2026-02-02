import {createAsyncThunk} from '@reduxjs/toolkit';
import type {RootState} from '../../types';
import {CAMERA_DEFAULT_CONSTRAINTS, type CameraConfig, type CameraDevice, createDefaultCameraConfig} from './cameras-types';
import {selectSelectedCameraConfigs} from './cameras-selectors';
import {selectServerEndpoints} from "@/store";

interface DetectCamerasResponse {
    cameras: Array<{
        index: number;
        name: string;
        vendor_id?: string;
        product_id?: string;
    }>;
}

export const detectCameras = createAsyncThunk<
    CameraDevice[],
    { filterVirtual?: boolean } | undefined,
    { state: RootState }
>('cameras/detect', async (args = {filterVirtual: true}, {getState}) => {
    const state = getState();
    const endpoints = selectServerEndpoints(state); // Get URLs from state
    const existingCameras = state.cameras.entities;

    const response = await fetch(endpoints.detectCameras, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(args),
    });

    if (!response.ok) {
        throw new Error(`Failed to detect cameras: ${response.statusText}`);
    }

    const data: DetectCamerasResponse = await response.json();

    return data.cameras.map((serverCamera) => {
        const cameraId = serverCamera.index.toString();
        const existingCamera = existingCameras[cameraId];

        return {
            index: serverCamera.index,
            deviceId: `${serverCamera.vendor_id || ''}${serverCamera.product_id || ''}`,
            cameraId,
            selected: existingCamera?.selected ?? true,
            status: 'AVAILABLE' as const,
            label: serverCamera.name,
            groupId: '',
            kind: 'videoinput',
            constraints: CAMERA_DEFAULT_CONSTRAINTS,
            config: existingCamera?.config || createDefaultCameraConfig(
                serverCamera.index,
                serverCamera.name,
                cameraId
            ),
        };
    });
});

export const connectToCameras = createAsyncThunk<
    { camera_configs: Record<string, CameraConfig> },
    void,
    { state: RootState }
>('cameras/connect', async (_, {getState}) => {
    const state = getState();
    const endpoints = selectServerEndpoints(state);
    const cameraConfigs = selectSelectedCameraConfigs(state);

    if (Object.keys(cameraConfigs).length === 0) {
        throw new Error('No camera devices selected for connection');
    }

    const response = await fetch(endpoints.createGroup, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({camera_configs: cameraConfigs}),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to connect to cameras');
    }

    return response.json();
});

export const updateCameraConfigs = createAsyncThunk<
    { camera_configs: Record<string, CameraConfig> },
    void,
    { state: RootState }
>('cameras/updateConfigs', async (_, {getState}) => {
    const state = getState();
    const endpoints = selectServerEndpoints(state);
    const cameraConfigs = selectSelectedCameraConfigs(state);

    const response = await fetch(endpoints.updateConfigs, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({camera_configs: cameraConfigs}),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update camera configs');
    }

    return response.json();
});
export const closeCameras = createAsyncThunk<
    void,                    // Return type
    void,                    // Argument type (no arguments)
    { state: RootState }     // ThunkAPI config
>(
    'cameras/close',
    async (_, {getState}) => {
        const state = getState();
        const endpoints = selectServerEndpoints(state);
        const response = await fetch(endpoints.closeAll, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`Failed to close cameras: ${response.statusText}`);
        }
    }
);

export const pauseUnpauseCameras = createAsyncThunk<
    void,                    // Return type
    void,                    // Argument type (no arguments)
    { state: RootState }     // ThunkAPI config
>(
    'cameras/pause',
    async (_, {getState}) => {
        const state = getState();
        const endpoints = selectServerEndpoints(state);
        const response = await fetch(endpoints.pauseUnpauseCameras, {method: 'GET'});

        if (!response.ok) {
            throw new Error(`Failed to pause/unpause cameras: ${response.statusText}`);
        }
    }
);
