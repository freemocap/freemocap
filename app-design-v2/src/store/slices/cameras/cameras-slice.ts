import {
    createSlice,
    type PayloadAction,
    type EntityState,
} from '@reduxjs/toolkit';
import type {CameraDevice, CameraConfig} from './cameras-types';
import { cameraAdapter } from './cameras-adapter';
import {
    detectCameras,
    connectToCameras,
    updateCameraConfigs,
    closeCameras,
} from './cameras-thunks';

interface CameraState extends EntityState<CameraDevice, string> {
    isLoading: boolean;
    error: string | null;
    connectionStatus: 'disconnected' | 'connecting' | 'connected';
}

const initialState: CameraState = cameraAdapter.getInitialState({
    isLoading: false,
    error: null,
    connectionStatus: 'disconnected',
});

export const cameraSlice = createSlice({
    name: 'cameras',
    initialState,
    reducers: {
        cameraStatusUpdated: (
            state,
            action: PayloadAction<{ cameraId: string; status: CameraDevice['status'] }>
        ) => {
            cameraAdapter.updateOne(state, {
                id: action.payload.cameraId,
                changes: { status: action.payload.status },
            });
        },
        cameraSelectionToggled: (state, action: PayloadAction<string>) => {
            const camera = state.entities[action.payload];
            if (camera) {
                const newSelected = !camera.selected;
                cameraAdapter.updateOne(state, {
                    id: action.payload,
                    changes: {
                        selected: newSelected,
                        config: {
                            ...camera.config,
                            use_this_camera: newSelected,
                        },
                    },
                });
            }
        },
        cameraConfigUpdated: (
            state,
            action: PayloadAction<{
                cameraId: string;
                config: Partial<CameraConfig>;
            }>
        ) => {
            const camera = state.entities[action.payload.cameraId];
            if (camera) {
                cameraAdapter.updateOne(state, {
                    id: action.payload.cameraId,
                    changes: {
                        config: {
                            ...camera.config,
                            ...action.payload.config,
                        },
                    },
                });
            }
        },
        configCopiedToAllCameras: (state, action: PayloadAction<string>) => {
            const sourceCamera = state.entities[action.payload];
            if (sourceCamera) {
                const configToCopy = {
                    resolution: sourceCamera.config.resolution,
                    color_channels: sourceCamera.config.color_channels,
                    pixel_format: sourceCamera.config.pixel_format,
                    exposure_mode: sourceCamera.config.exposure_mode,
                    exposure: sourceCamera.config.exposure,
                    framerate: sourceCamera.config.framerate,
                    rotation: sourceCamera.config.rotation,
                    capture_fourcc: sourceCamera.config.capture_fourcc,
                    writer_fourcc: sourceCamera.config.writer_fourcc,
                };

                const updates = Object.values(state.entities)
                    .filter((cam) =>
                        cam !== undefined && cam.cameraId !== action.payload
                    )
                    .map((camera) => ({
                        id: camera.cameraId,
                        changes: {
                            config: {
                                ...camera.config,
                                ...configToCopy,
                            },
                        },
                    }));
                cameraAdapter.updateMany(state, updates);
            }
        },
        errorCleared: (state) => {
            state.error = null;
        },
    },
    extraReducers: (builder) => {
        builder
            // Detect cameras
            .addCase(detectCameras.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(detectCameras.fulfilled, (state, action) => {
                state.isLoading = false;
                cameraAdapter.setAll(state, action.payload);
            })
            .addCase(detectCameras.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to detect cameras';
            })
            // Connect to cameras
            .addCase(connectToCameras.pending, (state) => {
                state.connectionStatus = 'connecting';
                state.error = null;
            })
            .addCase(connectToCameras.fulfilled, (state, action) => {
                state.connectionStatus = 'connected';
                // Update configs from server response
                const updates = Object.entries(action.payload.camera_configs).map(
                    ([cameraId, config]) => ({
                        id: cameraId,
                        changes: { config: config as CameraConfig },
                    })
                );
                cameraAdapter.updateMany(state, updates);
            })
            .addCase(connectToCameras.rejected, (state, action) => {
                state.connectionStatus = 'disconnected';
                state.error = action.error.message || 'Failed to connect to cameras';
            })
            // Update camera configs
            .addCase(updateCameraConfigs.fulfilled, (state, action) => {
                const updates = Object.entries(action.payload.camera_configs).map(
                    ([cameraId, config]) => ({
                        id: cameraId,
                        changes: { config: config as CameraConfig },
                    })
                );
                cameraAdapter.updateMany(state, updates);
            })
            // Close cameras
            .addCase(closeCameras.fulfilled, (state) => {
                state.connectionStatus = 'disconnected';
            });
    },
});

export const {
    cameraStatusUpdated,
    cameraSelectionToggled,
    cameraConfigUpdated,
    configCopiedToAllCameras,
    errorCleared,
} = cameraSlice.actions;
