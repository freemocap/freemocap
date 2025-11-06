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
    selectLastCalibrationRecordingPath,
    startCalibrationRecording,
    stopCalibrationRecording,
    updateCalibrationConfigOnServer,
} from "@/store";

export function useCalibration() {
    const dispatch = useAppDispatch();
    const calibrationState = useAppSelector(selectCalibration);
    const canStartRecording = useAppSelector(selectCanStartCalibrationRecording);
    const canCalibrate = useAppSelector(selectCanCalibrate);
    const lastCalibrationRecordingPath = useAppSelector(selectLastCalibrationRecordingPath);

    const updateConfig = useCallback(
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
        lastCalibrationRecordingPath,
        canStartRecording,
        canCalibrate,
        // Actions
        updateCalibrationConfig: updateConfig,
        startRecording,
        stopRecording,
        calibrate,
        clearError,
    };
}
