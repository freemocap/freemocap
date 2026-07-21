// cameras-thunks.ts
import {createAction, createAsyncThunk} from '@reduxjs/toolkit';
import {RootState} from '../../types';
import {serverUrls} from '@/services';
import {
    Camera,
    CameraConfig,
    CamerasConnectOrUpdateRequest,
    ConnectCamerasResponse,
    createDefaultCameraConfig,
    DetectCamerasRequest,
    DetectCamerasResponse,
} from './cameras-types';
import {selectSelectedCameraConfigs} from './cameras-selectors';
import {
    loadPersistedCameraSettings,
    PersistedCameraSettingsMap,
    savePersistedCameraSettings,
} from './camera-settings-storage';

// Dispatched before a connect request that includes RECOMMEND mode cameras.
// Handled by the slice to optimistically flip RECOMMEND → MANUAL so the UI
// clears immediately and the listener doesn't re-trigger during the long request.
export const recommendExposureSent = createAction('cameras/recommendExposureSent');

export const detectCameras = createAsyncThunk<
    Camera[],
    DetectCamerasRequest | undefined,
    { state: RootState }
>(
    'cameras/detect',
    async (request = { filterVirtual: true }) => {
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

        const detectedIds = new Set(data.cameras.map(c => c.camera_id));

        // Prune persisted entries for cameras that are no longer detected.

        const prunedPersisted: PersistedCameraSettingsMap = {};
        for (const [id, settings] of Object.entries(persisted)) {
            if (detectedIds.has(id)) {
                prunedPersisted[id] = settings;
            }
        }
        savePersistedCameraSettings(prunedPersisted);

        return data.cameras.map((serverCamera): Camera => {
            const cameraId = serverCamera.camera_id;
            const saved = prunedPersisted[cameraId];

            const defaultConfig = createDefaultCameraConfig(
                cameraId,
                serverCamera.index,
                serverCamera.name,
            );

            // Priority: persisted localStorage > defaults
            // (in-memory state for an already-known camera is merged in by the
            // reducer, using the state at fulfillment time rather than this
            // stale dispatch-time snapshot)
            const desiredConfig: CameraConfig = saved
                ? { ...defaultConfig, ...saved.desiredConfig }
                : { ...defaultConfig };

            const selected: boolean = saved?.selected ?? true;
            const realtimeEnabled: boolean = saved?.realtimeEnabled ?? true;

            return {
                id: cameraId,
                name: serverCamera.name,
                index: serverCamera.index,
                actualConfig: defaultConfig,
                desiredConfig,
                hasConfigMismatch: false,
                connectionStatus: 'available',
                selected,
                realtimeEnabled,
                deviceInfo: {
                    vendorId: serverCamera.vendor_id,
                    productId: serverCamera.product_id,
                },
                metrics: undefined,
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
    async (_, { getState, dispatch }) => {
        const state = getState();
        const cameraConfigs = selectSelectedCameraConfigs(state);

        if (Object.keys(cameraConfigs).length === 0) {
            throw new Error('No cameras selected for connection');
        }

        const hasRecommend = Object.values(cameraConfigs).some(
            c => c.exposure_mode === 'RECOMMEND'
        );

        const request: CamerasConnectOrUpdateRequest = { camera_configs: cameraConfigs };

        // Optimistically flip RECOMMEND → MANUAL before the request goes out so
        // the UI clears immediately and the listener won't queue another call.
        if (hasRecommend) {
            dispatch(recommendExposureSent());
        }

        // RECOMMEND triggers a slow backend algorithm; give it enough time.
        // Opening camera devices for the first time can also be much slower
        // than re-applying config to cameras that are already running.
        const anyConnected = state.cameras.cameras.some(c => c.connectionStatus === 'connected');
        const timeoutMs = hasRecommend ? 60_000 : anyConnected ? 3_000 : 15_000;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), timeoutMs);
        let response: Response;
        try {
            response = await fetch(serverUrls.endpoints.camerasConnectOrUpdate, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(request),
                signal: controller.signal,
            });
        } finally {
            clearTimeout(timeout);
        }

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
