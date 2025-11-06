// store/slices/calibration/calibration-slice.ts
import { createSlice, PayloadAction, createSelector } from '@reduxjs/toolkit';
import { RootState } from '../../types';
import {
    calibrateRecording,
    startCalibrationRecording,
    stopCalibrationRecording,
    updateCalibrationConfigOnServer,
} from "@/store/slices/calibration/calibration-thunks";

// ==================== Types ====================

export interface CalibrationConfig {
    liveTrackCharuco: boolean;
    charucoBoardXSquares: number;
    charucoBoardYSquares: number;
    charucoSquareLength: number;
    minSharedViewsPerCamera: number;
    autoStopOnMinViewCount: boolean;
}

export interface CalibrationState {
    config: CalibrationConfig;
    isRecording: boolean;
    recordingProgress: number;
    isLoading: boolean;
    error: string | null;
    lastCalibrationRecordingPath: string | null; // Store the path of the last calibration recording
}

// ==================== Initial State ====================

const initialState: CalibrationState = {
    config: {
        liveTrackCharuco: true,
        charucoBoardXSquares: 5,
        charucoBoardYSquares: 3,
        charucoSquareLength: 56,
        minSharedViewsPerCamera: 200,
        autoStopOnMinViewCount: true,
    },
    isRecording: false,
    recordingProgress: 0,
    isLoading: false,
    error: null,
    lastCalibrationRecordingPath: null,
};

// ==================== Slice ====================

export const calibrationSlice = createSlice({
    name: 'calibration',
    initialState,
    reducers: {
        calibrationConfigUpdated: (state, action: PayloadAction<Partial<CalibrationConfig>>) => {
            state.config = { ...state.config, ...action.payload };
        },

        calibrationProgressUpdated: (state, action: PayloadAction<number>) => {
            state.recordingProgress = action.payload;
        },

        calibrationErrorCleared: (state) => {
            state.error = null;
        },

        resetCalibrationState: () => initialState,
    },

    extraReducers: (builder) => {
        // Start Recording
        builder
            .addCase(startCalibrationRecording.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(startCalibrationRecording.fulfilled, (state, action) => {
                state.isLoading = false;
                state.isRecording = true;
                state.recordingProgress = 0;
                // Store the path returned from the server
                if (action.payload.calibrationRecordingPath) {
                    state.lastCalibrationRecordingPath = action.payload.calibrationRecordingPath;
                }
            })
            .addCase(startCalibrationRecording.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload || 'Failed to start recording';
            });

        // Stop Recording
        builder
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
                state.error = action.payload || 'Failed to stop recording';
            });

        // Calibrate Recording
        builder
            .addCase(calibrateRecording.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(calibrateRecording.fulfilled, (state) => {
                state.isLoading = false;
            })
            .addCase(calibrateRecording.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload || 'Failed to calibrate recording';
            });

        // Update Config on Server
        builder
            .addCase(updateCalibrationConfigOnServer.rejected, (state, action) => {
                state.error = action.payload || 'Failed to sync config to server';
            });
    },
});

// ==================== Selectors ====================

export const selectCalibration = (state: RootState) => state.calibration;
export const selectCalibrationConfig = (state: RootState) => state.calibration.config;
export const selectCalibrationIsLoading = (state: RootState) => state.calibration.isLoading;
export const selectCalibrationIsRecording = (state: RootState) => state.calibration.isRecording;
export const selectCalibrationProgress = (state: RootState) => state.calibration.recordingProgress;
export const selectCalibrationError = (state: RootState) => state.calibration.error;
export const selectLastCalibrationRecordingPath = (state: RootState) => state.calibration.lastCalibrationRecordingPath;

export const selectCanStartCalibrationRecording = createSelector(
    [selectCalibrationIsRecording, selectCalibrationIsLoading, (state: RootState) => state.recording.recordingDirectory],
    (isRecording, isLoading, recordingDirectory) => !isRecording && !isLoading && !!recordingDirectory
);

export const selectCanCalibrate = createSelector(
    [selectLastCalibrationRecordingPath, selectCalibrationIsLoading, selectCalibrationIsRecording],
    (lastRecordingPath, isLoading, isRecording) =>
        !!lastRecordingPath && !isLoading && !isRecording
);

// ==================== Actions Export ====================

export const {
    calibrationConfigUpdated,
    calibrationProgressUpdated,
    calibrationErrorCleared,
    resetCalibrationState
} = calibrationSlice.actions;

// ==================== Reducer Export ====================

export default calibrationSlice.reducer;
