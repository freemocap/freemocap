// store/slices/mocap/mocap-slice.ts
import { createSlice, PayloadAction, createSelector } from '@reduxjs/toolkit';
import { RootState } from '../../types';
import {
    processMocapRecording,
    startMocapRecording,
    stopMocapRecording,
    updateMocapConfigOnServer,
} from "@/store/slices/mocap/mocap-thunks";

// ==================== Types ====================

export interface MocapConfig {
}

export interface MocapDirectoryInfo {
    exists: boolean;
    canRecord: boolean; // true if directory doesn't exist OR exists but is empty
    canCalibrate: boolean; // true if has videos (either in synchronized_videos or root)
    cameraMocapTomlPath: string | null;
    hasSynchronizedVideos: boolean;
    hasVideos: boolean;
    errorMessage: string | null;
}

export interface MocapState {
    config: MocapConfig;
    isRecording: boolean;
    recordingProgress: number;
    isLoading: boolean;
    error: string | null;
    lastMocapRecordingPath: string | null; // Path from last recording
    manualMocapRecordingPath: string | null; // User-selected override path
    directoryInfo: MocapDirectoryInfo | null; // Info about the current mocap directory
}

// ==================== Initial State ====================

const initialState: MocapState = {
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
    lastMocapRecordingPath: null,
    manualMocapRecordingPath: null,
    directoryInfo: null,
};

// ==================== Slice ====================

export const mocapSlice = createSlice({
    name: 'mocap',
    initialState,
    reducers: {
        mocapConfigUpdated: (state, action: PayloadAction<Partial<MocapConfig>>) => {
            state.config = { ...state.config, ...action.payload };
        },

        mocapProgressUpdated: (state, action: PayloadAction<number>) => {
            state.recordingProgress = action.payload;
        },

        mocapErrorCleared: (state) => {
            state.error = null;
        },

        // New action to set manual path
        manualMocapRecordingPathChanged: (state, action: PayloadAction<string>) => {
            state.manualMocapRecordingPath = action.payload;
        },

        // New action to clear manual path (revert to default)
        manualMocapRecordingPathCleared: (state) => {
            state.manualMocapRecordingPath = null;
        },

        // New action to update directory info
        mocapDirectoryInfoUpdated: (state, action: PayloadAction<MocapDirectoryInfo>) => {
            state.directoryInfo = action.payload;
        },

        resetMocapState: () => initialState,
    },

    extraReducers: (builder) => {
        // Start Recording
        builder
            .addCase(startMocapRecording.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(startMocapRecording.fulfilled, (state, action) => {
                state.isLoading = false;
                state.isRecording = true;
                state.recordingProgress = 0;
                // Store the path returned from the server
                if (action.payload.mocapRecordingPath) {
                    state.lastMocapRecordingPath = action.payload.mocapRecordingPath;
                }
            })
            .addCase(startMocapRecording.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload || 'Failed to start recording';
            });

        // Stop Recording
        builder
            .addCase(stopMocapRecording.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(stopMocapRecording.fulfilled, (state) => {
                state.isLoading = false;
                state.isRecording = false;
                state.recordingProgress = 0;
            })
            .addCase(stopMocapRecording.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload || 'Failed to stop recording';
            });

        // Process Mocap Recording
        builder
            .addCase(processMocapRecording.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(processMocapRecording.fulfilled, (state) => {
                state.isLoading = false;
            })
            .addCase(processMocapRecording.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload || 'Failed to calibrate recording';
            });

        // Update Config on Server
        builder
            .addCase(updateMocapConfigOnServer.rejected, (state, action) => {
                state.error = action.payload || 'Failed to sync config to server';
            });
    },
});

// ==================== Selectors ====================

export const selectMocap = (state: RootState) => state.mocap;
export const selectMocapConfig = (state: RootState) => state.mocap.config;
export const selectMocapIsLoading = (state: RootState) => state.mocap.isLoading;
export const selectMocapIsRecording = (state: RootState) => state.mocap.isRecording;
export const selectMocapProgress = (state: RootState) => state.mocap.recordingProgress;
export const selectMocapError = (state: RootState) => state.mocap.error;
export const selectMocapDirectoryInfo = (state: RootState) => state.mocap.directoryInfo;

export const selectMocapRecordingPath = createSelector(
    [
        (state: RootState) => state.mocap.manualMocapRecordingPath,
        (state: RootState) => state.mocap.lastMocapRecordingPath,
        (state: RootState) => state.recording.computed,
    ],
    (manualPath, lastPath, recordingComputed) => {
        if (manualPath) return manualPath;
        if (lastPath) return lastPath;

        // Build mocap path from recording computed values
        const mocapFolderName = `${recordingComputed.recordingName}_mocap`;
        return `${recordingComputed.fullRecordingPath}/${mocapFolderName}`;
    }
);

// Selector to check if using manual path
export const selectIsUsingManualMocapPath = createSelector(
    [(state: RootState) => state.mocap.manualMocapRecordingPath],
    (manualPath) => manualPath !== null
);

export const selectCanStartMocapRecording = createSelector(
    [
        selectMocapIsRecording,
        selectMocapIsLoading,
        selectMocapRecordingPath,
        selectMocapDirectoryInfo
    ],
    (isRecording, isLoading, recordingPath, directoryInfo) => {
        // Can start if: not recording, not loading, have a path, and directory can be recorded to
        return !isRecording && !isLoading && !!recordingPath && (directoryInfo?.canRecord ?? true);
    }
);

export const selectCanProcessMocapRecording = createSelector(
    [
        selectMocapRecordingPath,
        selectMocapIsLoading,
        selectMocapIsRecording,
        selectMocapDirectoryInfo
    ],
    (mocapPath, isLoading, isRecording, directoryInfo) => {
        // Can process if: have path, not loading, not recording, and directory has videos
        return !!mocapPath && !isLoading && !isRecording && (directoryInfo?.canCalibrate ?? false);
    }
);

// ==================== Actions Export ====================

export const {
    mocapConfigUpdated,
    mocapProgressUpdated,
    mocapErrorCleared,
    manualMocapRecordingPathChanged,
    manualMocapRecordingPathCleared,
    mocapDirectoryInfoUpdated,
    resetMocapState
} = mocapSlice.actions;

// ==================== Reducer Export ====================

export default mocapSlice.reducer;
