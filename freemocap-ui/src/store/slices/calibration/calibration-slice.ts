import {CalibrationAlignmentMethodSchema, CalibrationBoardMode, CalibrationSolverMethodSchema} from "./calibration-types";
import {createSelector, createSlice, isAnyOf, PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '../../root-state-types';
import {loadFromStorage} from '@/store/persistence';
import {saveCalibrationTransform} from './calibration-save';
import {
    calibrateRecording,
    loadCalibrationForRecording,
    loadCalibrationToml,
    loadMostRecentCalibration, restoreCalibrationSelection,
    startCalibrationRecording,
    stopCalibrationRecording,
} from '@/store/slices/calibration/calibration-thunks';
import {
    selectActiveRecordingFullPath,
    selectActiveRecordingOrigin,
} from '@/store/slices/active-recording/active-recording-slice';

export type {
    CalibrationSolverMethod,
    CharucoBoardConfig,
    CalibrationConfig,
    CalibrationCameraData,
    LoadedCalibration,
} from './calibration-types';
import type { CalibrationConfig, LoadedCalibration } from './calibration-types';

export interface CalibrationDirectoryInfo {
    exists: boolean;
    canRecord: boolean;
    canCalibrate: boolean;
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
    isSaving: boolean;
    error: string | null;
    directoryInfo: CalibrationDirectoryInfo | null;
    loadedCalibration: LoadedCalibration | null;
    loadRequestId: string | null;
    mostRecentLoadAttempted: boolean;
    dismissedCalibrationPath: string | null;
}

const DEFAULT_CALIBRATION_CONFIG: CalibrationConfig = {
    boardMode: CalibrationBoardMode.AUTO,
    charucoBoard: { squares_x: 5, squares_y: 3, square_length_mm: 54 },
    minSharedViewsPerCamera: 200,
    autoStopOnMinViewCount: true,
    solverMethod: CalibrationSolverMethodSchema.enum.anipose,
    alignmentMethod: CalibrationAlignmentMethodSchema.enum.charuco,
};

const _persistedCalibrationConfig = loadFromStorage<CalibrationConfig | null>('calibration.config', null);

const initialState: CalibrationState = {
    config: {
        ...DEFAULT_CALIBRATION_CONFIG,
        ..._persistedCalibrationConfig,
        alignmentMethod: CalibrationAlignmentMethodSchema.nullable()
            .catch(DEFAULT_CALIBRATION_CONFIG.alignmentMethod)
            .parse(_persistedCalibrationConfig?.alignmentMethod),
        solverMethod: CalibrationSolverMethodSchema
            .catch(DEFAULT_CALIBRATION_CONFIG.solverMethod)
            .parse(_persistedCalibrationConfig?.solverMethod),
    },
    isRecording: false,
    recordingProgress: 0,
    isLoading: false,
    isSaving: false,
    error: null,
    directoryInfo: null,
    loadedCalibration: null,
    loadRequestId: null,
    mostRecentLoadAttempted: false,
    dismissedCalibrationPath: null,
};

export const calibrationSlice = createSlice({
    name: 'calibration',
    initialState,
    reducers: {
        calibrationConfigUpdated: (state, action: PayloadAction<Partial<CalibrationConfig>>) => {
            const config = { ...state.config, ...action.payload };
            config.alignmentMethod = CalibrationAlignmentMethodSchema.nullable().parse(config.alignmentMethod);
            state.config = config;
        },
        calibrationProgressUpdated: (state, action: PayloadAction<number>) => {
            state.recordingProgress = action.payload;
        },
        calibrationErrorCleared: (state) => {
            state.error = null;
        },
        calibrationDirectoryInfoUpdated: (state, action: PayloadAction<CalibrationDirectoryInfo>) => {
            state.directoryInfo = action.payload;
        },
        calibrationPipelineProgressReceived: (state, action: PayloadAction<{phase: string; detail: string}>) => {
            if (action.payload.phase === 'failed') state.error = action.payload.detail;
            if (action.payload.phase === 'complete' || action.payload.phase === 'failed') {
                state.isLoading = false;
            }
        },
        calibrationLoadedFromBundle: (state, action: PayloadAction<LoadedCalibration | null>) => {
            state.loadRequestId = null;
            state.loadedCalibration = action.payload;
        },
        calibrationAutoLoadDismissed: (state, action: PayloadAction<string | null>) => {
            state.dismissedCalibrationPath = action.payload;
        },
        resetCalibrationState: () => initialState,
    },
    extraReducers: (builder) => {
        builder
            .addCase(saveCalibrationTransform.pending, (state) => {
                state.isSaving = true;
                state.error = null;
            })
            .addCase(saveCalibrationTransform.fulfilled, (state, action) => {
                state.isSaving = false;
                if (state.loadedCalibration?.path === action.payload.path) {
                    state.loadedCalibration = action.payload;
                }
            })
            .addCase(saveCalibrationTransform.rejected, (state, action) => {
                state.isSaving = false;
                state.error = action.payload ?? action.error.message ?? 'Could not save calibration.';
            });
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

        builder
            .addMatcher(isAnyOf(loadCalibrationToml.pending, loadCalibrationForRecording.pending, loadMostRecentCalibration.pending, restoreCalibrationSelection.pending), (state, action) => {
                state.loadRequestId = action.meta.requestId;
                state.error = null;
                if (isAnyOf(loadMostRecentCalibration.pending, restoreCalibrationSelection.pending)(action)) state.mostRecentLoadAttempted = true;
            })
            .addMatcher(isAnyOf(loadCalibrationToml.fulfilled, loadCalibrationForRecording.fulfilled, loadMostRecentCalibration.fulfilled, restoreCalibrationSelection.fulfilled), (state, action) => {
                if (state.loadRequestId !== action.meta.requestId) return;
                state.loadRequestId = null;
                state.loadedCalibration = action.payload;
                state.dismissedCalibrationPath = null;
            })
            .addMatcher(isAnyOf(loadCalibrationToml.rejected, loadCalibrationForRecording.rejected, loadMostRecentCalibration.rejected, restoreCalibrationSelection.rejected), (state, action) => {
                if (state.loadRequestId !== action.meta.requestId) return;
                state.loadRequestId = null;
                if (action.meta.aborted) return;
                state.loadedCalibration = null;
                state.error = action.payload || action.error.message || 'Failed to load calibration';
            });
    },
});

export const selectCalibration = (state: RootState) => state.calibration;
export const selectCalibrationConfig = (state: RootState) => state.calibration.config;
export const selectCalibrationIsLoading = (state: RootState) => state.calibration.isLoading;
export const selectCalibrationIsRecording = (state: RootState) => state.calibration.isRecording;
export const selectCalibrationProgress = (state: RootState) => state.calibration.recordingProgress;
export const selectCalibrationError = (state: RootState) => state.calibration.error;
export const selectCalibrationDirectoryInfo = (state: RootState) => state.calibration.directoryInfo;
export const selectLoadedCalibration = (state: RootState) => state.calibration.loadedCalibration;
export const selectDismissedCalibrationPath = (state: RootState) => state.calibration.dismissedCalibrationPath;

export const selectCalibrationRecordingPath = selectActiveRecordingFullPath;

export const selectIsUsingManualCalibrationPath = createSelector(
    [selectActiveRecordingOrigin],
    (origin) => origin === 'browsed',
);

export const {
    calibrationConfigUpdated,
    calibrationProgressUpdated,
    calibrationErrorCleared,
    calibrationDirectoryInfoUpdated,
    calibrationPipelineProgressReceived,
    calibrationLoadedFromBundle,
    calibrationAutoLoadDismissed,
    resetCalibrationState,
} = calibrationSlice.actions;
