import {createSelector} from "@reduxjs/toolkit";
import {RootState} from "@/store/types";
import {
    BackendCalibrationConfig,
    BackendCalibrationSettings,
    BackendCameraState,
    BackendMocapConfig,
    BackendMocapSettings,
    BackendPipelineSettings,
    FreeMoCapSettings,
} from "./settings-types";

// ---------------------------------------------------------------------------
// Root selectors
// ---------------------------------------------------------------------------

export const selectServerSettings = (state: RootState): FreeMoCapSettings | null =>
    state.settings.settings;

export const selectServerSettingsVersion = (state: RootState): number =>
    state.settings.version;

export const selectServerSettingsInitialized = (state: RootState): boolean =>
    state.settings.isInitialized;

// ---------------------------------------------------------------------------
// Camera selectors
// ---------------------------------------------------------------------------

export const selectBackendCameras = createSelector(
    [selectServerSettings],
    (settings): Record<string, BackendCameraState> => settings?.cameras ?? {},
);

export const selectBackendCameraIds = createSelector(
    [selectBackendCameras],
    (cameras): string[] => Object.keys(cameras),
);

export const selectBackendConnectedCameraCount = createSelector(
    [selectBackendCameras],
    (cameras): number =>
        Object.values(cameras).filter((c) => c.status === "connected").length,
);

// ---------------------------------------------------------------------------
// Pipeline selectors
// ---------------------------------------------------------------------------

export const selectBackendPipeline = createSelector(
    [selectServerSettings],
    (settings): BackendPipelineSettings | null => settings?.pipeline ?? null,
);

export const selectBackendPipelineIsConnected = createSelector(
    [selectBackendPipeline],
    (pipeline): boolean => pipeline?.is_connected ?? false,
);

export const selectBackendPipelineId = createSelector(
    [selectBackendPipeline],
    (pipeline): string | null => pipeline?.pipeline_id ?? null,
);

// ---------------------------------------------------------------------------
// Calibration selectors
// ---------------------------------------------------------------------------

export const selectBackendCalibration = createSelector(
    [selectServerSettings],
    (settings): BackendCalibrationSettings | null => settings?.calibration ?? null,
);

export const selectBackendCalibrationConfig = createSelector(
    [selectBackendCalibration],
    (cal): BackendCalibrationConfig | null => cal?.config ?? null,
);

export const selectBackendCalibrationIsRecording = createSelector(
    [selectBackendCalibration],
    (cal): boolean => cal?.is_recording ?? false,
);

export const selectBackendCalibrationProgress = createSelector(
    [selectBackendCalibration],
    (cal): number => cal?.recording_progress ?? 0,
);

export const selectBackendHasCalibrationToml = createSelector(
    [selectBackendCalibration],
    (cal): boolean => cal?.has_calibration_toml ?? false,
);

// ---------------------------------------------------------------------------
// MoCap selectors
// ---------------------------------------------------------------------------

export const selectBackendMocap = createSelector(
    [selectServerSettings],
    (settings): BackendMocapSettings | null => settings?.mocap ?? null,
);

export const selectBackendMocapConfig = createSelector(
    [selectBackendMocap],
    (moc): BackendMocapConfig | null => moc?.config ?? null,
);

export const selectBackendMocapIsRecording = createSelector(
    [selectBackendMocap],
    (moc): boolean => moc?.is_recording ?? false,
);

export const selectBackendMocapProgress = createSelector(
    [selectBackendMocap],
    (moc): number => moc?.recording_progress ?? 0,
);
