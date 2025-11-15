// hooks/useMocap.ts
import {useCallback} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';

import {useElectronIPC} from '@/services';
import {
    manualMocapRecordingPathChanged,
    manualMocapRecordingPathCleared,
    MocapConfig,
    mocapConfigUpdated,
    mocapDirectoryInfoUpdated,
    mocapErrorCleared,
    processMocapRecording,
    selectCanProcessMocapRecording,
    selectCanStartMocapRecording,
    selectIsUsingManualMocapPath,
    selectMocap,
    selectMocapDirectoryInfo,
    selectMocapRecordingPath,
    startMocapRecording,
    stopMocapRecording,
    updateMocapConfigOnServer
} from "@/store/slices/mocap";

export function useMocap() {
    const dispatch = useAppDispatch();
    const { api, isElectron } = useElectronIPC();
    const mocapState = useAppSelector(selectMocap);
    const canStartRecording = useAppSelector(selectCanStartMocapRecording);
    const canProcessMocapRecording = useAppSelector(selectCanProcessMocapRecording);
    const mocapRecordingPath = useAppSelector(selectMocapRecordingPath);
    const directoryInfo = useAppSelector(selectMocapDirectoryInfo);
    const isUsingManualPath = useAppSelector(selectIsUsingManualMocapPath);

    const updateMocapConfig = useCallback(
        (updates: Partial<MocapConfig>) => {
            // Update local state first
            dispatch(mocapConfigUpdated(updates));
            // Then sync to server - this reads from the updated state
            dispatch(updateMocapConfigOnServer());
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
                const info = await api.fileSystem.validateMocapDirectory.query({ directoryPath });
                dispatch(mocapDirectoryInfoUpdated(info));
            } catch (error) {
                console.error('Failed to validate mocap directory:', error);
                // Don't throw - just log the error
            }
        },
        [dispatch, isElectron, api]
    );

    const setManualRecordingPath = useCallback(
        async (path: string) => {
            dispatch(manualMocapRecordingPathChanged(path));
            // Validate the new path
            await validateDirectory(path);
        },
        [dispatch, validateDirectory]
    );

    const clearManualRecordingPath = useCallback(() => {
        dispatch(manualMocapRecordingPathCleared());
    }, [dispatch]);

    const dispatchStartMocapRecording = useCallback(() => {
        dispatch(startMocapRecording());
    }, [dispatch]);

    const dispatchStopMocapRecording = useCallback(() => {
        dispatch(stopMocapRecording());
    }, [dispatch]);

    const dispatchProcessMocapRecording = useCallback(() => {
        dispatch(processMocapRecording());
    }, [dispatch]);

    const clearError = useCallback(() => {
        dispatch(mocapErrorCleared());
    }, [dispatch]);

    return {
        // State
        config: mocapState.config,
        error: mocapState.error,
        isLoading: mocapState.isLoading,
        isRecording: mocapState.isRecording,
        recordingProgress: mocapState.recordingProgress,
        mocapRecordingPath,
        directoryInfo,
        isUsingManualPath,
        canStartRecording,
        canProcessMocapRecording,
        // Actions
        updateMocapConfig,
        setManualRecordingPath,
        clearManualRecordingPath,
        validateDirectory,
        dispatchStartMocapRecording,
        dispatchStopMocapRecording,
        dispatchProcessMocapRecording,
        clearError,
    };
}
