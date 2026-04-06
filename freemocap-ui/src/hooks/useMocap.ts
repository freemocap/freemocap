import {useCallback} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {useElectronIPC} from '@/services';
import {
    MediapipeDetectorConfig,
    RealtimeFilterConfig,
    mocapDetectorConfigReplaced,
    mocapDetectorConfigUpdated,
    skeletonFilterConfigReplaced,
    skeletonFilterConfigUpdated,
    mocapDirectoryInfoUpdated,
    mocapErrorCleared,
    manualMocapRecordingPathChanged,
    manualMocapRecordingPathCleared,
    calibrationTomlPathChanged,
    calibrationTomlPathCleared,
    selectMocap,
    selectMocapDetectorConfig,
    selectSkeletonFilterConfig,
    selectMocapDirectoryInfo,
    selectMocapRecordingPath,
    selectCanProcessMocapRecording,
    selectCanStartMocapRecording,
    selectIsUsingManualMocapPath,
    selectCalibrationTomlPath,
    startMocapRecording,
    stopMocapRecording,
    processMocapRecording,
    updateMocapConfigOnServer,
} from "@/store/slices/mocap";

export function useMocap() {
    const dispatch = useAppDispatch();
    const {api, isElectron} = useElectronIPC();
    const mocapState = useAppSelector(selectMocap);
    const detectorConfig = useAppSelector(selectMocapDetectorConfig);
    const skeletonFilterConfig = useAppSelector(selectSkeletonFilterConfig);
    const canStartRecording = useAppSelector(selectCanStartMocapRecording);
    const canProcessMocapRecording = useAppSelector(selectCanProcessMocapRecording);
    const mocapRecordingPath = useAppSelector(selectMocapRecordingPath);
    const directoryInfo = useAppSelector(selectMocapDirectoryInfo);
    const isUsingManualPath = useAppSelector(selectIsUsingManualMocapPath);
    const calibrationTomlPath = useAppSelector(selectCalibrationTomlPath);

    const updateDetectorConfig = useCallback(
        (updates: Partial<MediapipeDetectorConfig>) => {
            dispatch(mocapDetectorConfigUpdated(updates));
            dispatch(updateMocapConfigOnServer());
        },
        [dispatch]
    );

    const replaceDetectorConfig = useCallback(
        (config: MediapipeDetectorConfig) => {
            dispatch(mocapDetectorConfigReplaced(config));
            dispatch(updateMocapConfigOnServer());
        },
        [dispatch]
    );

    const updateSkeletonFilterConfig = useCallback(
        (updates: Partial<RealtimeFilterConfig>) => {
            dispatch(skeletonFilterConfigUpdated(updates));
            dispatch(updateMocapConfigOnServer());
        },
        [dispatch]
    );

    const replaceSkeletonFilterConfig = useCallback(
        (config: RealtimeFilterConfig) => {
            dispatch(skeletonFilterConfigReplaced(config));
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
                const info = await api.fileSystem.validateMocapDirectory.query({directoryPath});
                dispatch(mocapDirectoryInfoUpdated(info));
            } catch (error) {
                console.error('Failed to validate mocap directory:', error);
            }
        },
        [dispatch, isElectron, api]
    );

    const setManualRecordingPath = useCallback(
        async (path: string) => {
            dispatch(manualMocapRecordingPathChanged(path));
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

    const setCalibrationTomlPath = useCallback(
        (path: string) => {
            dispatch(calibrationTomlPathChanged(path));
        },
        [dispatch]
    );

    const clearCalibrationTomlPath = useCallback(() => {
        dispatch(calibrationTomlPathCleared());
    }, [dispatch]);

    const clearError = useCallback(() => {
        dispatch(mocapErrorCleared());
    }, [dispatch]);

    return {
        // State
        config: mocapState.config,
        detectorConfig,
        skeletonFilterConfig,
        error: mocapState.error,
        isLoading: mocapState.isLoading,
        isRecording: mocapState.isRecording,
        recordingProgress: mocapState.recordingProgress,
        mocapRecordingPath,
        directoryInfo,
        isUsingManualPath,
        canStartRecording,
        canProcessMocapRecording,
        calibrationTomlPath,
        // Actions
        updateDetectorConfig,
        replaceDetectorConfig,
        updateSkeletonFilterConfig,
        replaceSkeletonFilterConfig,
        setManualRecordingPath,
        clearManualRecordingPath,
        dispatchStartMocapRecording,
        dispatchStopMocapRecording,
        dispatchProcessMocapRecording,
        validateDirectory,
        setCalibrationTomlPath,
        clearCalibrationTomlPath,
        clearError,
    };
}
