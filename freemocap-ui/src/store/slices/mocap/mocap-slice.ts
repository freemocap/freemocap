import {createSelector, createSlice, PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '../../types';
import {
    processMocapRecording,
    startMocapRecording,
    stopMocapRecording,
    updateMocapConfigOnServer,
} from "@/store/slices/mocap/mocap-thunks";

// ==================== Types ====================

/**
 * Mirrors skellytracker MediapipeModelComplexity enum.
 * 0 = LITE (fastest), 1 = FULL (balanced), 2 = HEAVY (most accurate)
 */
export type MediapipeModelComplexity = 0 | 1 | 2;

/**
 * Mirrors skellytracker MediapipeDetectorConfig.
 * Field names use snake_case to match the backend JSON.
 */
export interface MediapipeDetectorConfig {
    model_complexity: MediapipeModelComplexity;
    min_detection_confidence: number;
    min_tracking_confidence: number;
    confidence_threshold: number;
    static_image_mode: boolean;
    smooth_landmarks: boolean;
    enable_segmentation: boolean;
    smooth_segmentation: boolean;
    refine_face_landmarks: boolean;
}

/**
 * Mirrors backend EstimatorConfig (bone length estimation tuning).
 */
export interface EstimatorConfig {
    max_samples: number;
    min_samples_for_full_confidence: number;
    iqr_confidence_sensitivity: number;
}

/**
 * Mirrors backend RealtimeFilterConfig (skeleton smoothing + gating).
 * Field names use snake_case to match the backend JSON.
 */
export interface RealtimeFilterConfig {
    // One Euro Filter params
    min_cutoff: number;
    beta: number;
    d_cutoff: number;
    // FABRIK params
    fabrik_tolerance: number;
    fabrik_max_iterations: number;
    // Bone length estimation params
    height_meters: number;
    noise_sigma: number;
    estimator_config: EstimatorConfig;
    // Point gate params
    max_reprojection_error_px: number;
    max_velocity_m_per_s: number;
    max_rejected_streak: number;
}

/**
 * Mirrors backend MocapPipelineConfig.
 */
export interface MocapConfig {
    detector: MediapipeDetectorConfig;
    skeleton_filter: RealtimeFilterConfig;
}

/** Realtime preset matching MEDIAPIPE_TRACKER_REALTIME_PRESET on the backend. */
export const MEDIAPIPE_REALTIME_PRESET: MediapipeDetectorConfig = {
    model_complexity: 0,
    min_detection_confidence: 0.5,
    min_tracking_confidence: 0.5,
    confidence_threshold: 0.5,
    static_image_mode: false,
    smooth_landmarks: true,
    enable_segmentation: false,
    smooth_segmentation: false,
    refine_face_landmarks: true,
};

/** Posthoc preset matching MEDIAPIPE_TRACKER_POSTHOC_PRESET on the backend. */
export const MEDIAPIPE_POSTHOC_PRESET: MediapipeDetectorConfig = {
    model_complexity: 2,
    min_detection_confidence: 0.5,
    min_tracking_confidence: 0.5,
    confidence_threshold: 0.5,
    static_image_mode: false,
    smooth_landmarks: true,
    enable_segmentation: true,
    smooth_segmentation: true,
    refine_face_landmarks: true,
};

/** Default EstimatorConfig matching backend defaults. */
export const DEFAULT_ESTIMATOR_CONFIG: EstimatorConfig = {
    max_samples: 500,
    min_samples_for_full_confidence: 100,
    iqr_confidence_sensitivity: 10.0,
};

/** Default RealtimeFilterConfig matching backend defaults. */
export const DEFAULT_REALTIME_FILTER_CONFIG: RealtimeFilterConfig = {
    min_cutoff: 0.004,
    beta: 0.7,
    d_cutoff: 1.0,
    fabrik_tolerance: 1e-4,
    fabrik_max_iterations: 20,
    height_meters: 1.75,
    noise_sigma: 0.008,
    estimator_config: { ...DEFAULT_ESTIMATOR_CONFIG },
    max_reprojection_error_px: 40.0,
    max_velocity_m_per_s: 25.0,
    max_rejected_streak: 5,
};

export interface MocapDirectoryInfo {
    exists: boolean;
    canRecord: boolean;
    canCalibrate: boolean;
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
    lastMocapRecordingPath: string | null;
    manualMocapRecordingPath: string | null;
    directoryInfo: MocapDirectoryInfo | null;
}

// ==================== Initial State ====================

const initialState: MocapState = {
    config: {
        detector: { ...MEDIAPIPE_REALTIME_PRESET },
        skeleton_filter: { ...DEFAULT_REALTIME_FILTER_CONFIG },
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
        /** Replace the entire detector config (e.g. applying a preset). */
        mocapDetectorConfigReplaced: (state, action: PayloadAction<MediapipeDetectorConfig>) => {
            state.config.detector = action.payload;
        },

        /** Partially update individual detector fields. */
        mocapDetectorConfigUpdated: (state, action: PayloadAction<Partial<MediapipeDetectorConfig>>) => {
            state.config.detector = { ...state.config.detector, ...action.payload };
        },

        /** Replace the entire skeleton filter config. */
        skeletonFilterConfigReplaced: (state, action: PayloadAction<RealtimeFilterConfig>) => {
            state.config.skeleton_filter = action.payload;
        },

        /** Partially update individual skeleton filter fields. */
        skeletonFilterConfigUpdated: (state, action: PayloadAction<Partial<RealtimeFilterConfig>>) => {
            state.config.skeleton_filter = { ...state.config.skeleton_filter, ...action.payload };
        },

        mocapProgressUpdated: (state, action: PayloadAction<number>) => {
            state.recordingProgress = action.payload;
        },

        mocapErrorCleared: (state) => {
            state.error = null;
        },

        manualMocapRecordingPathChanged: (state, action: PayloadAction<string>) => {
            state.manualMocapRecordingPath = action.payload;
        },

        manualMocapRecordingPathCleared: (state) => {
            state.manualMocapRecordingPath = null;
        },

        mocapDirectoryInfoUpdated: (state, action: PayloadAction<MocapDirectoryInfo>) => {
            state.directoryInfo = action.payload;
        },

        resetMocapState: () => initialState,
    },

    extraReducers: (builder) => {
        builder
            .addCase(startMocapRecording.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(startMocapRecording.fulfilled, (state, action) => {
                state.isLoading = false;
                state.isRecording = true;
                state.recordingProgress = 0;
                if (action.payload.mocapRecordingPath) {
                    state.lastMocapRecordingPath = action.payload.mocapRecordingPath;
                }
            })
            .addCase(startMocapRecording.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload || 'Failed to start recording';
            });

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
                state.error = action.payload || 'Failed to process recording';
            });

        builder
            .addCase(updateMocapConfigOnServer.rejected, (state, action) => {
                state.error = action.payload || 'Failed to sync config to server';
            });
    },
});

// ==================== Selectors ====================

export const selectMocap = (state: RootState) => state.mocap;
export const selectMocapConfig = (state: RootState) => state.mocap.config;
export const selectMocapDetectorConfig = (state: RootState) => state.mocap.config.detector;
export const selectSkeletonFilterConfig = (state: RootState) => state.mocap.config.skeleton_filter;
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

        const mocapFolderName = `${recordingComputed.recordingName}_mocap`;
        return `${recordingComputed.fullRecordingPath}/${mocapFolderName}`;
    }
);

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
        return !!mocapPath && !isLoading && !isRecording && (directoryInfo?.canCalibrate ?? false);
    }
);

// ==================== Actions Export ====================

export const {
    mocapDetectorConfigReplaced,
    mocapDetectorConfigUpdated,
    skeletonFilterConfigReplaced,
    skeletonFilterConfigUpdated,
    mocapProgressUpdated,
    mocapErrorCleared,
    manualMocapRecordingPathChanged,
    manualMocapRecordingPathCleared,
    mocapDirectoryInfoUpdated,
    resetMocapState
} = mocapSlice.actions;

export default mocapSlice.reducer;
