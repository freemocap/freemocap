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

export type BoardType = '5x3' | '7x5' | 'custom';

export interface BoardSize {
    rows: number;
    cols: number;
}

export interface CalibrationConfig {
    boardType: BoardType;
    boardSize: BoardSize;
    squareSize: number;
    minSharedViews: number;
    autoProcess: boolean;
    liveTrackCharuco: boolean;
    calibrationRecordingPath: string;
}

export interface CalibrationState {
    config: CalibrationConfig;
    isRecording: boolean;
    recordingProgress: number;
    isLoading: boolean;
    error: string | null;
}

// ==================== Initial State ====================

const initialState: CalibrationState = {
    config: {
        boardType: '5x3',
        boardSize: { rows: 5, cols: 3 },
        squareSize: 54.0,
        minSharedViews: 200,
        autoProcess: true,
        liveTrackCharuco: true,
        calibrationRecordingPath: '',
    },
    isRecording: false,
    recordingProgress: 0,
    isLoading: false,
    error: null,
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
            .addCase(startCalibrationRecording.fulfilled, (state) => {
                state.isLoading = false;
                state.isRecording = true;
                state.recordingProgress = 0;
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

export const selectCanStartCalibrationRecording = createSelector(
    [selectCalibrationIsRecording, selectCalibrationIsLoading],
    (isRecording, isLoading) => !isRecording && !isLoading
);

export const selectCanCalibrate = createSelector(
    [selectCalibrationConfig, selectCalibrationIsLoading, selectCalibrationIsRecording],
    (config, isLoading, isRecording) =>
        config.calibrationRecordingPath.length > 0 && !isLoading && !isRecording
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

// ==================== Helper Functions ====================

export function getBoardSizeForType(boardType: BoardType): BoardSize {
    switch (boardType) {
        case '5x3':
            return { rows: 5, cols: 3 };
        case '7x5':
            return { rows: 7, cols: 5 };
        case 'custom':
            return { rows: 7, cols: 5 };
    }
}
