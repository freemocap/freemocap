// cameras-thunks.ts
import { createAsyncThunk } from '@reduxjs/toolkit';
import { RootState } from '../../types';
import { serverUrls } from '@/services';
import {
    Camera,
    CameraConfig,
    DetectCamerasRequest,
    DetectCamerasResponse,
    CamerasConnectOrUpdateRequest,
    ConnectCamerasResponse,
    createDefaultCameraConfig,
} from './cameras-types';
import { selectSelectedCameraConfigs } from './cameras-selectors';
import {
    loadPersistedCameraSettings,
    savePersistedCameraSettings,
    PersistedCameraSettingsMap,
} from './camera-settings-storage';

export const detectCameras = createAsyncThunk<
    Camera[],
    DetectCamerasRequest | undefined,
    { state: RootState }
>(
    'cameras/detect',
    async (request = { filterVirtual: true }, { getState }) => {
        const state = getState();
        const existingCameras = state.cameras.cameras;

        const response = await fetch(serverUrls.endpoints.detectCameras, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            throw new Error(`Failed to detect cameras: ${response.statusText}`);
        }

        const data: DetectCamerasResponse = await response.json();

        // Load persisted settings from localStorage
        let persisted: PersistedCameraSettingsMap = {};
        try {
            persisted = loadPersistedCameraSettings();
        } catch {
            // Storage was corrupted and has been cleared — proceed with defaults
        }

        const detectedIds = new Set(data.cameras.map(c => c.index.toString()));

        // Prune persisted entries for cameras that are no longer detected
        const prunedPersisted: PersistedCameraSettingsMap = {};
        for (const [id, settings] of Object.entries(persisted)) {
            if (detectedIds.has(id)) {
                prunedPersisted[id] = settings;
            }
        }
        savePersistedCameraSettings(prunedPersisted);

        return data.cameras.map((serverCamera): Camera => {
            const cameraId = serverCamera.index.toString();
            const existing = existingCameras.find(cam => cam.id === cameraId);
            const saved = prunedPersisted[cameraId];

            const defaultConfig = createDefaultCameraConfig(
                cameraId,
                serverCamera.index,
                serverCamera.name,
            );

            // Priority: existing in-memory state > persisted localStorage > defaults
            const desiredConfig: CameraConfig = existing?.desiredConfig
                ?? (saved ? { ...defaultConfig, ...saved.desiredConfig } : { ...defaultConfig });

            const selected: boolean = existing?.selected
                ?? saved?.selected
                ?? true;

            return {
                id: cameraId,
                name: serverCamera.name,
                index: serverCamera.index,
                actualConfig: existing?.actualConfig || defaultConfig,
                desiredConfig,
                hasConfigMismatch: existing?.hasConfigMismatch ?? false,
                connectionStatus: 'available',
                selected,
                deviceInfo: {
                    vendorId: serverCamera.vendor_id,
                    productId: serverCamera.product_id,
                },
                metrics: existing?.metrics,
            };
        });
    }
);

export const camerasConnectOrUpdate = createAsyncThunk<
    ConnectCamerasResponse,
    void,
    { state: RootState }
>(
    'cameras/connect',
    async (_, { getState }) => {
        const state = getState();
        const cameraConfigs = selectSelectedCameraConfigs(state);

        if (Object.keys(cameraConfigs).length === 0) {
            throw new Error('No cameras selected for connection');
        }

        const request: CamerasConnectOrUpdateRequest = { camera_configs: cameraConfigs };

        const response = await fetch(serverUrls.endpoints.camerasConnectOrUpdate, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to connect to cameras');
        }

        return response.json() as Promise<ConnectCamerasResponse>;
    }
);


export const closeCameras = createAsyncThunk<void, void, { state: RootState }>(
    'cameras/close',
    async () => {
        const response = await fetch(serverUrls.endpoints.closeAll, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`Failed to close cameras: ${response.statusText}`);
        }
    }
);

export const pauseUnpauseCameras = createAsyncThunk<void, void, { state: RootState }>(
    'cameras/pause',
    async () => {
        const response = await fetch(serverUrls.endpoints.pauseUnpauseCameras, {
            method: 'GET',
        });

        if (!response.ok) {
            throw new Error(`Failed to pause/unpause cameras: ${response.statusText}`);
        }
    }
);
