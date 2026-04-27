import {createSelector, createSlice, PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '../../types';
import {loadFromStorage} from '@/store/persistence';
import {
    calibrateRecording,
    loadCalibrationForRecording,
    loadCalibrationToml,
    startCalibrationRecording,
    stopCalibrationRecording,
} from '@/store/slices/calibration/calibration-thunks';
import {
    selectActiveRecordingFullPath,
    selectActiveRecordingOrigin,
    selectEffectiveRecordingPath,
} from '@/store/slices/active-recording/active-recording-slice';

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
    directoryInfo: CalibrationDirectoryInfo | null;
    loadedCalibration: LoadedCalibration | null;
}

const DEFAULT_CALIBRATION_CONFIG: CalibrationConfig = {
    charucoBoard: { squares_x: 5, squares_y: 3, square_length_mm: 54 },
    minSharedViewsPerCamera: 200,
    autoStopOnMinViewCount: true,
    solverMethod: 'anipose',
    useGroundplane: false,
};

const _persistedCalibrationConfig = loadFromStorage<CalibrationConfig | null>('calibration.config', null);

const initialState: CalibrationState = {
    config: _persistedCalibrationConfig ?? { ...DEFAULT_CALIBRATION_CONFIG },
    isRecording: false,
    recordingProgress: 0,
    isLoading: false,
    error: null,
    directoryInfo: null,
    loadedCalibration: null,
};

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
            .addCase(loadCalibrationToml.fulfilled, (state, action) => {
                if (action.payload) {
                    state.loadedCalibration = action.payload;
                }
            })
            .addCase(loadCalibrationToml.rejected, (state) => {
                state.loadedCalibration = null;
            });

        builder
            .addCase(loadCalibrationForRecording.fulfilled, (state, action) => {
                if (action.payload) {
                    state.loadedCalibration = action.payload;
                }
            })
            .addCase(loadCalibrationForRecording.rejected, (state, action) => {
                console.warn('[calibration] loadCalibrationForRecording rejected:', action.payload);
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

export const selectCalibration = (state: RootState) => state.calibration;
export const selectCalibrationConfig = (state: RootState) => state.calibration.config;
export const selectCalibrationIsLoading = (state: RootState) => state.calibration.isLoading;
export const selectCalibrationIsRecording = (state: RootState) => state.calibration.isRecording;
export const selectCalibrationProgress = (state: RootState) => state.calibration.recordingProgress;
export const selectCalibrationError = (state: RootState) => state.calibration.error;
export const selectCalibrationDirectoryInfo = (state: RootState) => state.calibration.directoryInfo;
export const selectLoadedCalibration = (state: RootState) => state.calibration.loadedCalibration;

export const selectCalibrationRecordingPath = selectActiveRecordingFullPath;

export const selectIsUsingManualCalibrationPath = createSelector(
    [selectActiveRecordingOrigin],
    (origin) => origin === 'browsed',
);

export const selectCanStartCalibrationRecording = createSelector(
    [
        selectCalibrationIsRecording,
        selectCalibrationIsLoading,
        selectEffectiveRecordingPath,
        selectCalibrationDirectoryInfo
    ],
    (isRecording, isLoading, effectivePath, directoryInfo) => {
        return !isRecording && !isLoading && !!effectivePath && (directoryInfo?.canRecord ?? true);
    }
);

export const selectCanCalibrate = createSelector(
    [
        selectCalibrationRecordingPath,
        selectCalibrationIsLoading,
        selectCalibrationIsRecording,
        selectCalibrationDirectoryInfo,
    ],
    (recordingPath, isLoading, isRecording, directoryInfo) => {
        return (
            !!recordingPath &&
            !isLoading &&
            !isRecording &&
            (directoryInfo?.canCalibrate ?? true)
        );
    }
);

export const {
    calibrationConfigUpdated,
    calibrationProgressUpdated,
    calibrationErrorCleared,
    calibrationDirectoryInfoUpdated,
    resetCalibrationState,
} = calibrationSlice.actions;
