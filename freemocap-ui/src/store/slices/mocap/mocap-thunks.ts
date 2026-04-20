import {createAsyncThunk} from "@reduxjs/toolkit";
import {RootState} from "@/store";
import {selectMocapRecordingPath} from "./mocap-slice";
import {getDetailedErrorMessage} from "@/store/slices/thunk-helpers";
import {serverUrls} from "@/services";

export const startMocapRecording = createAsyncThunk<
    { success: boolean; message?: string; mocapRecordingPath?: string },
    void,
    { state: RootState; rejectValue: string }
>(
    'mocap/startRecording',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState();
            const mocapTaskConfig = state.mocap.config;
            const mocapRecordingDirectory = selectMocapRecordingPath(state);

            if (!mocapRecordingDirectory) {
                return rejectWithValue('Recording directory is not set');
            }

            const calibrationTomlPath = state.mocap.calibrationTomlPath;
            const blender = state.blender;
            const configWithCalibration = {
                ...mocapTaskConfig,
                calibrationTomlPath: calibrationTomlPath,
                exportToBlender: blender.exportToBlenderEnabled,
                blenderExePath: blender.blenderExePath ?? blender.detectedBlenderExePath,
                autoOpenBlendFile: blender.autoOpenBlendFile,
            };

            console.log('🎬 Starting mocap recording with:', {
                mocapRecordingDirectory,
                mocapTaskConfig: configWithCalibration,
            });

            const response = await fetch(serverUrls.endpoints.mocapStartRecording, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mocapRecordingDirectory,
                    mocapTaskConfig: configWithCalibration,
                }),
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            console.log('✅ Started mocap recording:', result);
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to start mocap recording:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

export const stopMocapRecording = createAsyncThunk<
    { success: boolean },
    void,
    { state: RootState; rejectValue: string }
>(
    'mocap/stopRecording',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState();
            const mocapTaskConfig = state.mocap.config;


            const calibrationTomlPath = state.mocap.calibrationTomlPath;
            const blender = state.blender;
            const configWithCalibration = {
                ...mocapTaskConfig,
                calibrationTomlPath: calibrationTomlPath,
                exportToBlender: blender.exportToBlenderEnabled,
                blenderExePath: blender.blenderExePath ?? blender.detectedBlenderExePath,
                autoOpenBlendFile: blender.autoOpenBlendFile,
            };

            console.log(`🎬 Stopping mocap recording and starting mocap with: ${JSON.stringify(configWithCalibration, null, 2)}`);

            const response = await fetch(serverUrls.endpoints.mocapStopRecording, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({mocapTaskConfig: configWithCalibration}),
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            console.log('✅ Stopped mocap recording:', result);
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to stop mocap recording:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

export const processMocapRecording = createAsyncThunk<
    { success: boolean; message?: string; results?: unknown },
    void,
    { state: RootState; rejectValue: string }
>(
    'mocap/processMocapRecording',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState();
            const mocapTaskConfig = state.mocap.config;
            const mocapRecordingDirectory = selectMocapRecordingPath(state);

            if (!mocapRecordingDirectory) {
                return rejectWithValue('No mocap recording path available. Please set a recording directory or record a mocap first.');
            }

            console.log('🔧 Calibrating recording:', {
                mocapRecordingDirectory,
                mocapTaskConfig,
            });

            const calibrationTomlPath = state.mocap.calibrationTomlPath;
            const blender = state.blender;
            const configWithCalibration = {
                ...mocapTaskConfig,
                calibrationTomlPath: calibrationTomlPath,
                exportToBlender: blender.exportToBlenderEnabled,
                blenderExePath: blender.blenderExePath ?? blender.detectedBlenderExePath,
                autoOpenBlendFile: blender.autoOpenBlendFile,
            };

            const response = await fetch(serverUrls.endpoints.processMocapRecording, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mocapRecordingDirectory,
                    mocapTaskConfig: configWithCalibration,
                }),
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            console.log('✅ Mocap completed:', result);
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to process recording:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);
