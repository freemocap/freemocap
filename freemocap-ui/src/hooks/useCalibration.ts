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
    startCalibrationRecording,
    stopCalibrationRecording,
    updateCalibrationConfigOnServer,
} from "@/store";

export function useCalibration() {
    const dispatch = useAppDispatch();
    const state = useAppSelector(selectCalibration);
    const canStartRecording = useAppSelector(selectCanStartCalibrationRecording);
    const canCalibrate = useAppSelector(selectCanCalibrate);

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
        config: state.config,
        error: state.error,
        isLoading: state.isLoading,
        isRecording: state.isRecording,
        recordingProgress: state.recordingProgress,
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
