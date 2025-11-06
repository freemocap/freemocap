// hooks/useCalibration.ts
import { useCallback } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
    calibrateRecording,
    CalibrationConfig,
    calibrationConfigUpdated,
    calibrationErrorCleared,
    selectCalibration,
    selectCanCalibrate,
    selectCanStartCalibrationRecording,
    selectCalibrationRecordingPath,
    startCalibrationRecording,
    stopCalibrationRecording,
    updateCalibrationConfigOnServer,
} from "@/store";

export function useCalibration() {
    const dispatch = useAppDispatch();
    const calibrationState = useAppSelector(selectCalibration);
    const canStartRecording = useAppSelector(selectCanStartCalibrationRecording);
    const canCalibrate = useAppSelector(selectCanCalibrate);
    const calibrationRecordingPath = useAppSelector(selectCalibrationRecordingPath);

    const updateCalibrationConfig = useCallback(
        (updates: Partial<CalibrationConfig>) => {
            // Update local state first
            dispatch(calibrationConfigUpdated(updates));
            // Then sync to server - this reads from the updated state
            dispatch(updateCalibrationConfigOnServer());
        },
        [dispatch]
    );

    const startRecording = useCallback(() => {
        dispatch(startCalibrationRecording());
    }, [dispatch]);

    const stopRecording = useCallback(() => {
        dispatch(stopCalibrationRecording());
    }, [dispatch]);

    const calibrate = useCallback(() => {
        dispatch(calibrateRecording());
    }, [dispatch]);

    const clearError = useCallback(() => {
        dispatch(calibrationErrorCleared());
    }, [dispatch]);

    return {
        // State
        config: calibrationState.config,
        error: calibrationState.error,
        isLoading: calibrationState.isLoading,
        isRecording: calibrationState.isRecording,
        recordingProgress: calibrationState.recordingProgress,
        calibrationRecordingPath,
        canStartRecording,
        canCalibrate,
        // Actions
        updateCalibrationConfig,
        startRecording,
        stopRecording,
        calibrate,
        clearError,
    };
}
