import {createSlice, PayloadAction} from '@reduxjs/toolkit';
import {areConfigsEqual, CameraConfig, CamerasState, extractConfigSettings,} from './cameras-types';
import {detectCameras,} from './cameras-thunks';
import {closePipeline, connectRealtimePipeline} from '../pipeline/pipeline-thunks';
import {serverSettingsCleared, serverSettingsUpdated} from '../settings/settings-slice';


const initialState: CamerasState = {
    cameras: [],
    isLoading: false,
    error: null,
};

export const cameraSlice = createSlice({
    name: 'cameras',
    initialState,
    reducers: {
        // ========== Selection ==========
        cameraSelectionToggled: (state, action: PayloadAction<string>) => {
            const camera = state.cameras.find(cam => cam.id === action.payload);
            if (camera) {
                camera.selected = !camera.selected;
                camera.desiredConfig.use_this_camera = camera.selected;
            }
        },

        // ========== Configuration ==========
        cameraDesiredConfigUpdated: (
            state,
            action: PayloadAction<{
                cameraId: string;
                config: Partial<CameraConfig>
            }>
        ) => {
            const camera = state.cameras.find(
                cam => cam.id === action.payload.cameraId
            );
            if (camera) {
                camera.desiredConfig = {...camera.desiredConfig, ...action.payload.config};
                camera.hasConfigMismatch = !areConfigsEqual(camera.actualConfig, camera.desiredConfig);
            }
        },

        configCopiedToAll: (state, action: PayloadAction<string>) => {
            const sourceCamera = state.cameras.find(cam => cam.id === action.payload);
            if (!sourceCamera) return;

            const settings = extractConfigSettings(sourceCamera.desiredConfig);

            state.cameras.forEach(camera => {
                if (camera.id !== action.payload) {
                    camera.desiredConfig = {
                        ...camera.desiredConfig,
                        ...settings
                    };
                    camera.hasConfigMismatch = !areConfigsEqual(camera.actualConfig, camera.desiredConfig);
                }
            });
        },
    },

    extraReducers: (builder) => {
        builder
            // ========== Detect Cameras ==========
            .addCase(detectCameras.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(detectCameras.fulfilled, (state, action) => {
                state.isLoading = false;
                state.cameras = action.payload;
            })
            .addCase(detectCameras.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to detect cameras';
            })

            // ========== Connect Pipeline (HTTP) ==========
            .addCase(connectRealtimePipeline.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(connectRealtimePipeline.fulfilled, (state, action) => {
                state.isLoading = false;
                Object.entries(action.payload.camera_configs).forEach(
                    ([cameraId, config]) => {
                        const camera = state.cameras.find(cam => cam.id === cameraId);
                        if (camera) {
                            camera.actualConfig = config as CameraConfig;
                            camera.hasConfigMismatch = !areConfigsEqual(camera.actualConfig, camera.desiredConfig);
                            camera.connectionStatus = 'connected';
                        }
                    }
                );
            })
            .addCase(connectRealtimePipeline.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to connect to cameras';
            })

            // ========== Close Pipeline (HTTP) ==========
            .addCase(closePipeline.fulfilled, (state) => {
                state.cameras.forEach(camera => {
                    camera.connectionStatus = 'available';
                    camera.metrics = undefined;
                    camera.hasConfigMismatch = false;
                });
            })

            // ========== WebSocket settings/state — sync camera connection status ==========
            .addCase(serverSettingsUpdated, (state, action) => {
                const backendCameras = action.payload.settings.cameras;
                for (const camera of state.cameras) {
                    const backendCam = backendCameras[camera.id];
                    if (backendCam) {
                        // Sync connection status from authoritative backend state
                        if (backendCam.status === 'connected') {
                            camera.connectionStatus = 'connected';
                        } else if (backendCam.status === 'error') {
                            camera.connectionStatus = 'error';
                        } else {
                            camera.connectionStatus = 'available';
                        }
                    } else {
                        // Backend doesn't know about this camera — it's not connected
                        camera.connectionStatus = 'available';
                    }
                }
            })

            // ========== WebSocket disconnected — clear all connected state ==========
            .addCase(serverSettingsCleared, (state) => {
                state.cameras.forEach(camera => {
                    camera.connectionStatus = 'available';
                    camera.metrics = undefined;
                });
            });
    },
});

export const {
    cameraSelectionToggled,
    cameraDesiredConfigUpdated,
    configCopiedToAll,
} = cameraSlice.actions;
