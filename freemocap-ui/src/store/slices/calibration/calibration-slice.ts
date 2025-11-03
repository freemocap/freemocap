// calibration-slice.ts
import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import {
    CalibrationConfig,
    CalibrationState,
    createDefaultCalibrationConfig,
} from './calibration-types';
import { startCalibrationRecording, stopCalibrationRecording, calibrateRecording } from './calibration-thunks';

const initialState: CalibrationState = {
    config: createDefaultCalibrationConfig(),
    isRecording: false,
    recordingProgress: 0,
    isLoading: false,
    error: null,
};

export const calibrationSlice = createSlice({
    name: 'calibration',
    initialState,
    reducers: {
        calibrationConfigUpdated: (state, action: PayloadAction<Partial<CalibrationConfig>>) => {
            state.config = { ...state.config, ...action.payload };
        },

        calibrationRecordingProgressUpdated: (state, action: PayloadAction<number>) => {
            state.recordingProgress = action.payload;
        },

        calibrationConfigReset: (state) => {
            state.config = createDefaultCalibrationConfig();
            state.isRecording = false;
            state.recordingProgress = 0;
            state.error = null;
        },

        calibrationErrorCleared: (state) => {
            state.error = null;
        },
    },

    extraReducers: (builder) => {
        builder
            // ========== Start Recording ==========
            .addCase(startCalibrationRecording.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(startCalibrationRecording.fulfilled, (state) => {
                state.isLoading = false;
                state.isRecording = true;
                state.recordingProgress = 0;
            })
            .addCase(startCalibrationRecording.rejected, (state, action) => {
                state.isLoading = false;
                state.isRecording = false;
                state.error = action.payload as string || action.error.message || 'Failed to start recording';
            })

            // ========== Stop Recording ==========
            .addCase(stopCalibrationRecording.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(stopCalibrationRecording.fulfilled, (state) => {
                state.isLoading = false;
                state.isRecording = false;
                state.recordingProgress = 0;
            })
            .addCase(stopCalibrationRecording.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload as string || action.error.message || 'Failed to stop recording';
            })

            // ========== Calibrate Recording ==========
            .addCase(calibrateRecording.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(calibrateRecording.fulfilled, (state) => {
                state.isLoading = false;
            })
            .addCase(calibrateRecording.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload as string || action.error.message || 'Failed to calibrate recording';
            });
    },
});

export const {
    calibrationConfigUpdated,
    calibrationRecordingProgressUpdated,
    calibrationConfigReset,
    calibrationErrorCleared,
} = calibrationSlice.actions;
