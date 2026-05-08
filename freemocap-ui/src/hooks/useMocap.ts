import {useCallback} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {store} from '@/store';
import {useElectronIPC} from '@/services';
import {
    calibrationTomlPathChanged,
    calibrationTomlPathCleared,
    MediapipeDetectorConfig,
    MocapDirectoryInfo,
    mocapDetectorConfigReplaced,
    mocapDetectorConfigUpdated,
    mocapDirectoryInfoUpdated,
    mocapErrorCleared,
    processMocapRecording,
    RealtimeFilterConfig,
    selectCalibrationTomlPath,
    selectCanProcessMocapRecording,
    selectCanStartMocapRecording,
    selectIsUsingManualMocapPath,
    selectMocap,
    selectMocapDetectorConfig,
    selectMocapDirectoryInfo,
    selectMocapRecordingPath,
    selectSkeletonFilterConfig,
    skeletonFilterConfigReplaced,
    skeletonFilterConfigUpdated,
    startMocapRecording,
    stopMocapRecording,
} from "@/store/slices/mocap";

function mocapDirectoryInfoEqual(a: MocapDirectoryInfo | null, b: MocapDirectoryInfo): boolean {
    if (!a) return false;
    return (
        a.exists === b.exists &&
        a.canRecord === b.canRecord &&
        a.canCalibrate === b.canCalibrate &&
        a.hasSynchronizedVideos === b.hasSynchronizedVideos &&
        a.hasVideos === b.hasVideos &&
        a.cameraMocapTomlPath === b.cameraMocapTomlPath &&
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
        },
        [dispatch]
    );

    const replaceDetectorConfig = useCallback(
        (config: MediapipeDetectorConfig) => {
            dispatch(mocapDetectorConfigReplaced(config));
        },
        [dispatch]
    );

    const updateSkeletonFilterConfig = useCallback(
        (updates: Partial<RealtimeFilterConfig>) => {
            dispatch(skeletonFilterConfigUpdated(updates));
        },
        [dispatch]
    );

    const replaceSkeletonFilterConfig = useCallback(
        (config: RealtimeFilterConfig) => {
            dispatch(skeletonFilterConfigReplaced(config));
        },
        [dispatch]
    );

    // Local-only variants — update Redux state without triggering a server call.
    // Used when the caller (e.g. RealtimePipelineConfigTree) manages server sync itself.
    const updateDetectorConfigLocalOnly = useCallback(
        (updates: Partial<MediapipeDetectorConfig>) => {
            dispatch(mocapDetectorConfigUpdated(updates));
        },
        [dispatch]
    );

    const replaceDetectorConfigLocalOnly = useCallback(
        (config: MediapipeDetectorConfig) => {
            dispatch(mocapDetectorConfigReplaced(config));
        },
        [dispatch]
    );

    const updateSkeletonFilterConfigLocalOnly = useCallback(
        (updates: Partial<RealtimeFilterConfig>) => {
            dispatch(skeletonFilterConfigUpdated(updates));
        },
        [dispatch]
    );

    const replaceSkeletonFilterConfigLocalOnly = useCallback(
        (config: RealtimeFilterConfig) => {
            dispatch(skeletonFilterConfigReplaced(config));
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
                const current = store.getState().mocap.directoryInfo;
                if (!mocapDirectoryInfoEqual(current, info)) {
                    dispatch(mocapDirectoryInfoUpdated(info));
                }
            } catch (error) {
                console.error('Failed to validate mocap directory:', error);
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
        processingProgress: mocapState.processingProgress,
        processingPhase: mocapState.processingPhase,
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
        updateDetectorConfigLocalOnly,
        replaceDetectorConfigLocalOnly,
        updateSkeletonFilterConfigLocalOnly,
        replaceSkeletonFilterConfigLocalOnly,
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
