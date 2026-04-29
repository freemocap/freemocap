// hooks/useCalibration.ts
import {useCallback} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {store} from '@/store';
import {useElectronIPC} from '@/services';
import {
    calibrateRecording,
    CalibrationConfig,
    calibrationConfigUpdated,
    CalibrationDirectoryInfo,
    calibrationDirectoryInfoUpdated,
    calibrationErrorCleared,
    selectCalibration,
    selectCalibrationDirectoryInfo,
    selectCalibrationRecordingPath,
    selectCanCalibrate,
    selectCanStartCalibrationRecording,
    selectIsUsingManualCalibrationPath,
    startCalibrationRecording,
    stopCalibrationRecording,
} from "@/store/slices/calibration";

function calibrationDirectoryInfoEqual(a: CalibrationDirectoryInfo | null, b: CalibrationDirectoryInfo): boolean {
    if (!a) return false;
    return (
        a.exists === b.exists &&
        a.canRecord === b.canRecord &&
        a.canCalibrate === b.canCalibrate &&
        a.hasSynchronizedVideos === b.hasSynchronizedVideos &&
        a.hasVideos === b.hasVideos &&
        a.cameraCalibrationTomlPath === b.cameraCalibrationTomlPath &&
        a.lastSuccessfulCalibrationTomlPath === b.lastSuccessfulCalibrationTomlPath &&
        a.errorMessage === b.errorMessage
    );
}
import {pathRecomputed} from "@/store/slices/recording";
import {
    activeRecordingCleared,
    activeRecordingSet,
    splitParentAndName,
} from "@/store/slices/active-recording/active-recording-slice";

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
                const current = store.getState().calibration.directoryInfo;
                if (!calibrationDirectoryInfoEqual(current, info)) {
                    dispatch(calibrationDirectoryInfoUpdated(info));
                }
            } catch (error) {
                console.error('Failed to validate calibration directory:', error);
                // Don't throw - just log the error
            }
        },
        [dispatch, isElectron, api]
    );

    const setManualRecordingPath = useCallback(
        async (path: string) => {
            const parsed = splitParentAndName(path);
            if (parsed) {
                dispatch(activeRecordingSet({
                    recordingName: parsed.recordingName,
                    baseDirectory: parsed.baseDirectory,
                    origin: 'browsed',
                }));
            }
            await validateDirectory(path);
        },
        [dispatch, validateDirectory]
    );

    const clearManualRecordingPath = useCallback(() => {
        dispatch(activeRecordingCleared());
        dispatch(pathRecomputed());
    }, [dispatch]);

    const dispatchStartCalibrationRecording = useCallback(() => {
        dispatch(startCalibrationRecording());
    }, [dispatch]);

    const dispatchStopCalibrationRecording = useCallback(() => {
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
        dispatchStartCalibrationRecording,
        dispatchStopCalibrationRecording,
        calibrateSelectedRecording: calibrate,
        clearError,
    };
}
