// hooks/useCalibration.ts
import { useCallback } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
    calibrateRecording,
    CalibrationConfig,
    calibrationConfigUpdated,
    calibrationErrorCleared,
    calibrationDirectoryInfoUpdated,
    manualCalibrationRecordingPathChanged,
    manualCalibrationRecordingPathCleared,
    selectCalibration,
    selectCanCalibrate,
    selectCanStartCalibrationRecording,
    selectCalibrationRecordingPath,
    selectCalibrationDirectoryInfo,
    selectIsUsingManualCalibrationPath,
    startCalibrationRecording,
    stopCalibrationRecording,
    updateCalibrationConfigOnServer,
} from "@/store";
import { useElectronIPC } from '@/services';

export function useCalibration() {
    const dispatch = useAppDispatch();
    const { api, isElectron } = useElectronIPC();
    const calibrationState = useAppSelector(selectCalibration);
    const canStartRecording = useAppSelector(selectCanStartCalibrationRecording);
    const canCalibrate = useAppSelector(selectCanCalibrate);
    const calibrationRecordingPath = useAppSelector(selectCalibrationRecordingPath);
    const directoryInfo = useAppSelector(selectCalibrationDirectoryInfo);
    const isUsingManualPath = useAppSelector(selectIsUsingManualCalibrationPath);

    const updateCalibrationConfig = useCallback(
        (updates: Partial<CalibrationConfig>) => {
            // Update local state first
            dispatch(calibrationConfigUpdated(updates));
            // Then sync to server - this reads from the updated state
            dispatch(updateCalibrationConfigOnServer());
        },
        [dispatch]
    );

    const validateDirectory = useCallback(
        async (directoryPath: string) => {
            if (!isElectron || !api) {
                console.warn('Electron API not available - skipping directory validation');
                return;
            }

            try {
                const info = await api.fileSystem.validateCalibrationDirectory.query({ directoryPath });
                dispatch(calibrationDirectoryInfoUpdated(info));
            } catch (error) {
                console.error('Failed to validate calibration directory:', error);
                // Don't throw - just log the error
            }
        },
        [dispatch, isElectron, api]
    );

    const setManualRecordingPath = useCallback(
        async (path: string) => {
            dispatch(manualCalibrationRecordingPathChanged(path));
            // Validate the new path
            await validateDirectory(path);
        },
        [dispatch, validateDirectory]
    );

    const clearManualRecordingPath = useCallback(() => {
        dispatch(manualCalibrationRecordingPathCleared());
    }, [dispatch]);

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
        directoryInfo,
        isUsingManualPath,
        canStartRecording,
        canCalibrate,
        // Actions
        updateCalibrationConfig,
        setManualRecordingPath,
        clearManualRecordingPath,
        validateDirectory,
        startRecording,
        stopRecording,
        calibrate,
        clearError,
    };
}
