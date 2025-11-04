import {createAsyncThunk} from "@reduxjs/toolkit";
import {RootState} from "@/store";
import {serverUrls} from "@/hooks/server-urls";

export const startCalibrationRecording = createAsyncThunk<
    { success: boolean; message?: string },
    void,
    { state: RootState; rejectValue: string }
>(
    'calibration/startRecording',
    async (_, {getState, rejectWithValue}) => {
        try {
            const state = getState();
            const response = await fetch(serverUrls.endpoints.calibrationStartRecording, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({config: state.calibration.config}),
            });

            if (!response.ok) {
                return rejectWithValue(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            return rejectWithValue(error instanceof Error ? error.message : 'Unknown error');
        }
    }
);

export const stopCalibrationRecording = createAsyncThunk<
    { success: boolean },
    void,
    { rejectValue: string }
>(
    'calibration/stopRecording',
    async (_, {rejectWithValue}) => {
        try {
            const response = await fetch(serverUrls.endpoints.calibrationStopRecording, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
            });

            if (!response.ok) {
                return rejectWithValue(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            return rejectWithValue(error instanceof Error ? error.message : 'Unknown error');
        }
    }
);

export const calibrateRecording = createAsyncThunk<
    { success: boolean; message?: string; results?: unknown },
    void,
    { state: RootState; rejectValue: string }
>(
    'calibration/calibrateRecording',
    async (_, {getState, rejectWithValue}) => {
        try {
            const state = getState();
            const {calibrationRecordingPath, ...config} = state.calibration.config;

            const response = await fetch(serverUrls.endpoints.calibrateRecording, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    calibrationRecordingPath,
                    config
                }),
            });

            if (!response.ok) {
                return rejectWithValue(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            return rejectWithValue(error instanceof Error ? error.message : 'Unknown error');
        }
    }
);

export const updateCalibrationConfigOnServer = createAsyncThunk<
    { success: boolean; message?: string },
    void,
    { state: RootState; rejectValue: string }
>(
    'calibration/updateConfig',
    async (_, {getState, rejectWithValue}) => {
        try {
            const state = getState();
            const response = await fetch(serverUrls.endpoints.updateCalibrationConfig, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({config: state.calibration.config}),
            });

            if (!response.ok) {
                return rejectWithValue(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            return rejectWithValue(error instanceof Error ? error.message : 'Unknown error');
        }
    }
);
