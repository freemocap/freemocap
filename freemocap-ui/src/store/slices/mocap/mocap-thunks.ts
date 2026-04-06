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
            const configWithCalibration = {
                ...mocapTaskConfig,
                calibrationTomlPath: calibrationTomlPath,
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
            const configWithCalibration = {
                ...mocapTaskConfig,
                calibrationTomlPath: calibrationTomlPath,
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
            const configWithCalibration = {
                ...mocapTaskConfig,
                calibrationTomlPath: calibrationTomlPath,
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

export const updateMocapConfigOnServer = createAsyncThunk<
    { success: boolean; message?: string },
    void,
    { state: RootState; rejectValue: string }
>(
    'mocap/updateConfig',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState();
            const config = state.mocap.config;

            console.log('⚙️ Updating mocap config on server:', config);

            const response = await fetch(serverUrls.endpoints.updateMocapConfig, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ config }),
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            console.log('✅ Config updated on server:', result);
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to update config on server:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);
