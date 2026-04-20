import {createSelector, createSlice, PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '../../types';
import {
    calibrateRecording,
    loadCalibrationToml,
    startCalibrationRecording,
    stopCalibrationRecording,
} from "@/store/slices/calibration/calibration-thunks";

// ==================== Types ====================

export type CalibrationSolverMethod = 'anipose' | 'pyceres';

export interface CharucoBoardConfig {
    squares_x: number;
    squares_y: number;
    square_length_mm: number;
}

export interface CalibrationConfig {
    charucoBoard: CharucoBoardConfig;
    minSharedViewsPerCamera: number;
    autoStopOnMinViewCount: boolean;
    solverMethod: CalibrationSolverMethod;
    useGroundplane: boolean;
}

export interface CalibrationDirectoryInfo {
    exists: boolean;
    canRecord: boolean;
    canCalibrate: boolean;
    cameraCalibrationTomlPath: string | null;
    lastSuccessfulCalibrationTomlPath: string | null;
    hasSynchronizedVideos: boolean;
    hasVideos: boolean;
    errorMessage: string | null;
}

export interface CalibrationCameraData {
    id: string;
    name: string;
    size: [number, number];
    matrix: number[][];
    distortions: number[];
    rotation: [number, number, number];
    translation: [number, number, number];
    world_orientation: number[][];
    world_position: [number, number, number];
}

export interface LoadedCalibration {
    path: string;
    mtimeMs: number;
    cameras: CalibrationCameraData[];
    metadata: Record<string, any> | null;
}

export interface CalibrationState {
    config: CalibrationConfig;
    isRecording: boolean;
    recordingProgress: number;
    isLoading: boolean;
    error: string | null;
    lastCalibrationRecordingPath: string | null;
    manualCalibrationRecordingPath: string | null;
    directoryInfo: CalibrationDirectoryInfo | null;
    loadedCalibration: LoadedCalibration | null;
}

// ==================== Initial State ====================

const initialState: CalibrationState = {
    config: {
        charucoBoard: { squares_x: 5, squares_y: 3, square_length_mm: 54 },
        minSharedViewsPerCamera: 200,
        autoStopOnMinViewCount: true,
        solverMethod: 'anipose',
        useGroundplane: false,
    },
    isRecording: false,
    recordingProgress: 0,
    isLoading: false,
    error: null,
    lastCalibrationRecordingPath: null,
    manualCalibrationRecordingPath: null,
    directoryInfo: null,
    loadedCalibration: null,
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

        manualCalibrationRecordingPathChanged: (state, action: PayloadAction<string>) => {
            state.manualCalibrationRecordingPath = action.payload;
        },

        manualCalibrationRecordingPathCleared: (state) => {
            state.manualCalibrationRecordingPath = null;
        },

        lastCalibrationRecordingPathCleared: (state) => {
            state.lastCalibrationRecordingPath = null;
        },

        calibrationDirectoryInfoUpdated: (state, action: PayloadAction<CalibrationDirectoryInfo>) => {
            state.directoryInfo = action.payload;
        },

        resetCalibrationState: () => initialState,
    },

    extraReducers: (builder) => {
        builder
            .addCase(startCalibrationRecording.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(startCalibrationRecording.fulfilled, (state, action) => {
                state.isLoading = false;
                state.isRecording = true;
                state.recordingProgress = 0;
                if (action.payload.calibrationRecordingPath) {
                    state.lastCalibrationRecordingPath = action.payload.calibrationRecordingPath;
                }
            })
            .addCase(startCalibrationRecording.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload || 'Failed to start recording';
            });

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

        builder
            .addCase(loadCalibrationToml.fulfilled, (state, action) => {
                if (action.payload) {
                    state.loadedCalibration = action.payload;
                }
            })
            .addCase(loadCalibrationToml.rejected, (state) => {
                state.loadedCalibration = null;
            });

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
export const selectLoadedCalibration = (state: RootState) => state.calibration.loadedCalibration;

export const selectCalibrationRecordingPath = createSelector(
    [
        (state: RootState) => state.calibration.manualCalibrationRecordingPath,
        (state: RootState) => state.calibration.lastCalibrationRecordingPath,
        (state: RootState) => state.recording.computed,
    ],
    (manualPath, lastPath, recordingComputed) => {
        if (manualPath) return manualPath;
        if (lastPath) return lastPath;

        const calibrationFolderName = `${recordingComputed.recordingName}_calibration`;
        return `${recordingComputed.fullRecordingPath}/${calibrationFolderName}`;
    }
);

export const selectIsUsingManualCalibrationPath = createSelector(
    [
        (state: RootState) => state.calibration.manualCalibrationRecordingPath,
        (state: RootState) => state.calibration.lastCalibrationRecordingPath,
    ],
    (manualPath, lastPath) => manualPath !== null || lastPath !== null
);

export const selectCanStartCalibrationRecording = createSelector(
    [
        selectCalibrationIsRecording,
        selectCalibrationIsLoading,
        selectCalibrationRecordingPath,
        selectCalibrationDirectoryInfo
    ],
    (isRecording, isLoading, recordingPath, directoryInfo) => {
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
    lastCalibrationRecordingPathCleared,
    calibrationDirectoryInfoUpdated,
    resetCalibrationState
} = calibrationSlice.actions;

export default calibrationSlice.reducer;
