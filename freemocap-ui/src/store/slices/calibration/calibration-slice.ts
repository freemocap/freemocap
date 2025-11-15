// store/slices/calibration/calibration-slice.ts
import {createSelector, createSlice, PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '../../types';
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

export interface CalibrationDirectoryInfo {
    exists: boolean;
    canRecord: boolean; // true if directory doesn't exist OR exists but is empty
    canCalibrate: boolean; // true if has videos (either in synchronized_videos or root)
    cameraCalibrationTomlPath: string | null;
    hasSynchronizedVideos: boolean;
    hasVideos: boolean;
    errorMessage: string | null;
}

export interface CalibrationState {
    config: CalibrationConfig;
    isRecording: boolean;
    recordingProgress: number;
    isLoading: boolean;
    error: string | null;
    lastCalibrationRecordingPath: string | null; // Path from last recording
    manualCalibrationRecordingPath: string | null; // User-selected override path
    directoryInfo: CalibrationDirectoryInfo | null; // Info about the current calibration directory
}

// ==================== Initial State ====================

const initialState: CalibrationState = {
    config: {
        liveTrackCharuco: true,
        charucoBoardXSquares: 5,
        charucoBoardYSquares: 3,
        charucoSquareLength: 1,
        minSharedViewsPerCamera: 200,
        autoStopOnMinViewCount: true,
    },
    isRecording: false,
    recordingProgress: 0,
    isLoading: false,
    error: null,
    lastCalibrationRecordingPath: null,
    manualCalibrationRecordingPath: null,
    directoryInfo: null,
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

        // New action to set manual path
        manualCalibrationRecordingPathChanged: (state, action: PayloadAction<string>) => {
            state.manualCalibrationRecordingPath = action.payload;
        },

        // New action to clear manual path (revert to default)
        manualCalibrationRecordingPathCleared: (state) => {
            state.manualCalibrationRecordingPath = null;
        },

        // New action to update directory info
        calibrationDirectoryInfoUpdated: (state, action: PayloadAction<CalibrationDirectoryInfo>) => {
            state.directoryInfo = action.payload;
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
export const selectCalibrationDirectoryInfo = (state: RootState) => state.calibration.directoryInfo;

export const selectCalibrationRecordingPath = createSelector(
    [
        (state: RootState) => state.calibration.manualCalibrationRecordingPath,
        (state: RootState) => state.calibration.lastCalibrationRecordingPath,
        (state: RootState) => state.recording.computed,
    ],
    (manualPath, lastPath, recordingComputed) => {
        if (manualPath) return manualPath;
        if (lastPath) return lastPath;

        // Build calibration path from recording computed values
        const calibrationFolderName = `${recordingComputed.recordingName}_calibration`;
        return `${recordingComputed.fullRecordingPath}/${calibrationFolderName}`;
    }
);

// Selector to check if using manual path
export const selectIsUsingManualCalibrationPath = createSelector(
    [(state: RootState) => state.calibration.manualCalibrationRecordingPath],
    (manualPath) => manualPath !== null
);

export const selectCanStartCalibrationRecording = createSelector(
    [
        selectCalibrationIsRecording,
        selectCalibrationIsLoading,
        selectCalibrationRecordingPath,
        selectCalibrationDirectoryInfo
    ],
    (isRecording, isLoading, recordingPath, directoryInfo) => {
        // Can start if: not recording, not loading, have a path, and directory can be recorded to
        return !isRecording && !isLoading && !!recordingPath && (directoryInfo?.canRecord ?? true);
    }
);

export const selectCanCalibrate = createSelector(
    [
        selectCalibrationRecordingPath,
        selectCalibrationIsLoading,
        selectCalibrationIsRecording,
        selectCalibrationDirectoryInfo
    ],
    (calibrationPath, isLoading, isRecording, directoryInfo) => {
        // Can calibrate if: have path, not loading, not recording, and directory has videos
        return !!calibrationPath && !isLoading && !isRecording && (directoryInfo?.canCalibrate ?? false);
    }
);

// ==================== Actions Export ====================

export const {
    calibrationConfigUpdated,
    calibrationProgressUpdated,
    calibrationErrorCleared,
    manualCalibrationRecordingPathChanged,
    manualCalibrationRecordingPathCleared,
    calibrationDirectoryInfoUpdated,
    resetCalibrationState
} = calibrationSlice.actions;

// ==================== Reducer Export ====================

export default calibrationSlice.reducer;
