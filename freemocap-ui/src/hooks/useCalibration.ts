// useCalibration.ts
import { useCallback } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
    CalibrationConfig,
    calibrationConfigReset,
    calibrationConfigUpdated,
    calibrationRecordingProgressUpdated,
    calibrationErrorCleared,
    selectCalibrationConfig,
    selectCanCalibrateRecording,
    selectCanStartCalibrationRecording,
    selectIsRecording,
    selectRecordingProgress,
    selectCalibrationIsLoading,
    selectCalibrationError,
    startCalibrationRecording,
    stopCalibrationRecording,
    calibrateRecording,
} from '@/store/slices/calibration';

export interface UseCalibrationReturn {
    // State
    config: CalibrationConfig;
    isRecording: boolean;
    recordingProgress: number;
    isLoading: boolean;
    error: string | null;

    // Derived state
    canStartRecording: boolean;
    canCalibrateRecording: boolean;

    // Actions
    updateConfig: (updates: Partial<CalibrationConfig>) => void;
    updateRecordingProgress: (progress: number) => void;
    resetConfig: () => void;
    clearError: () => void;

    // Async actions
    startCalibrationRecording: () => void;
    stopCalibrationRecording: () => void;
    calibrateRecording: () => void;
}

export function useCalibration(): UseCalibrationReturn {
    const dispatch = useAppDispatch();

    // Selectors
    const config = useAppSelector(selectCalibrationConfig);
    const isRecording = useAppSelector(selectIsRecording);
    const recordingProgress = useAppSelector(selectRecordingProgress);
    const isLoading = useAppSelector(selectCalibrationIsLoading);
    const error = useAppSelector(selectCalibrationError);
    const canStartRecording = useAppSelector(selectCanStartCalibrationRecording);
    const canCalibrateRecording = useAppSelector(selectCanCalibrateRecording);

    // Sync actions
    const updateConfig = useCallback(
        (updates: Partial<CalibrationConfig>) => {
            dispatch(calibrationConfigUpdated(updates));
        },
        [dispatch]
    );

    const updateRecordingProgress = useCallback(
        (progress: number) => {
            dispatch(calibrationRecordingProgressUpdated(progress));
        },
        [dispatch]
    );

    const resetConfig = useCallback(() => {
        dispatch(calibrationConfigReset());
    }, [dispatch]);

    const clearError = useCallback(() => {
        dispatch(calibrationErrorCleared());
    }, [dispatch]);

    // Async actions
    const handleCalibrationStartRecording = useCallback(() => {
        dispatch(startCalibrationRecording());
    }, [dispatch]);

    const handleCalibrationStopRecording = useCallback(() => {
        dispatch(stopCalibrationRecording());
    }, [dispatch]);

    const handleCalibrateRecording = useCallback(() => {
        dispatch(calibrateRecording());
    }, [dispatch]);

    return {
        config,
        isRecording,
        recordingProgress,
        isLoading,
        error,
        canStartRecording,
        canCalibrateRecording,
        updateConfig,
        updateRecordingProgress,
        resetConfig,
        clearError,
        startCalibrationRecording: handleCalibrationStartRecording,
        stopCalibrationRecording: handleCalibrationStopRecording,
        calibrateRecording: handleCalibrateRecording,
    };
}
