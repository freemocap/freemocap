// calibration-thunks.ts
import {createAsyncThunk} from '@reduxjs/toolkit';
import {
    CalibrateRecordingRequest,
    CalibrateRecordingResponse,
    StartRecordingRequest,
    StartRecordingResponse,
} from './calibration-types';
import {RootState} from '../../types';

// Base URL helper - could be imported from a config file
const getApiUrl = (path: string): string => {
    return `http://localhost:8006${path}`;
};

// ==================== Start Recording Thunk ====================
export const startCalibrationRecording = createAsyncThunk<
    StartRecordingResponse,
    void,
    { state: RootState }
>(
    'calibration/startRecording',
    async (_, { getState, rejectWithValue }) => {
        const state = getState();
        const config = state.calibration.config;

        const request: StartRecordingRequest = { config };

        const response = await fetch(getApiUrl('/freemocap/calibration/recording/start'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            return rejectWithValue(`Failed to start recording: ${response.statusText}`);
        }

        const data: StartRecordingResponse = await response.json();

        if (!data.success) {
            return rejectWithValue(data.message || 'Failed to start recording');
        }

        return data;
    }
);

// ==================== Stop Recording Thunk ====================
export const stopCalibrationRecording = createAsyncThunk<
    { success: boolean },
    void,
    { state: RootState }
>(
    'calibration/stopRecording',
    async (_, { rejectWithValue }) => {
        const response = await fetch(getApiUrl('/freemocap/calibration/recording/stop'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });

        if (!response.ok) {
            return rejectWithValue(`Failed to stop recording: ${response.statusText}`);
        }

        return await response.json();
    }
);

// ==================== Calibrate Recording Thunk ====================
export const calibrateRecording = createAsyncThunk<
    CalibrateRecordingResponse,
    void,
    { state: RootState }
>(
    'calibration/calibrateRecording',
    async (_, { getState, rejectWithValue }) => {
        const state = getState();
        const { calibrationPath, ...configWithoutPath } = state.calibration.config;

        const request: CalibrateRecordingRequest = {
            calibrationPath,
            config: configWithoutPath,
        };

        const response = await fetch(getApiUrl('/freemocap/calibration/process'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            return rejectWithValue(`Failed to calibrate recording: ${response.statusText}`);
        }

        const data: CalibrateRecordingResponse = await response.json();

        if (!data.success) {
            return rejectWithValue(data.message || 'Failed to calibrate recording');
        }

        return data;
    }
);
