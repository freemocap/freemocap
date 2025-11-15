// cameras-slice.ts
import {createSlice, PayloadAction} from '@reduxjs/toolkit';
import {areConfigsEqual, CameraConfig, CamerasState, extractConfigSettings,} from './cameras-types';
import {detectCameras,} from './cameras-thunks';
import {closePipeline, connectRealtimePipeline} from '../pipeline/pipeline-thunks';


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
        // User updates desired config
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
                // Check if there's now a mismatch
                camera.hasConfigMismatch = !areConfigsEqual(camera.actualConfig, camera.desiredConfig);
            }
        },

        configCopiedToAll: (state, action: PayloadAction<string>) => {
            const sourceCamera = state.cameras.find(cam => cam.id === action.payload);
            if (!sourceCamera) return;

            // Extract copyable settings (exclude identity fields)
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

            // ========== Connect Pipeline ==========
            .addCase(connectRealtimePipeline.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(connectRealtimePipeline.fulfilled, (state, action) => {
                state.isLoading = false;
                // Update camera actual configs from server response
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

            // ========== Close Pipeline ==========
            .addCase(closePipeline.fulfilled, (state) => {
                state.cameras.forEach(camera => {
                    camera.connectionStatus = 'available';
                    camera.metrics = undefined;
                    camera.hasConfigMismatch = false;
                });
            });
    },
});

export const {
    cameraSelectionToggled,
    cameraDesiredConfigUpdated,
    configCopiedToAll,
} = cameraSlice.actions;
