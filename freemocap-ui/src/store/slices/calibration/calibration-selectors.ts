// calibration-selectors.ts
import { createSelector } from '@reduxjs/toolkit';
import { RootState } from '../../types';

// ========== Basic Selectors ==========
export const selectCalibrationConfig = (state: RootState) => state.calibration.config;
export const selectIsRecording = (state: RootState) => state.calibration.isRecording;
export const selectRecordingProgress = (state: RootState) => state.calibration.recordingProgress;
export const selectCalibrationIsLoading = (state: RootState) => state.calibration.isLoading;
export const selectCalibrationError = (state: RootState) => state.calibration.error;

// ========== Validation Selectors ==========
export const selectCanStartCalibrationRecording = createSelector(
    [selectIsRecording, selectCalibrationIsLoading],
    (isRecording, isLoading) => !isRecording && !isLoading
);

export const selectCanCalibrateRecording = createSelector(
    [selectCalibrationConfig, selectCalibrationIsLoading, selectIsRecording],
    (config, isLoading, isRecording) =>
        config.calibrationPath.length > 0 && !isLoading && !isRecording
);
