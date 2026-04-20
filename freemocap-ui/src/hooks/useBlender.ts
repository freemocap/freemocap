import {useCallback, useEffect} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {
    autoOpenBlendFileToggled,
    blenderErrorCleared,
    blenderExePathChanged,
    blenderExePathCleared,
    detectBlender,
    exportRecordingToBlender,
    exportToBlenderToggled,
    selectBlender,
    selectEffectiveBlenderExePath,
} from '@/store/slices/blender';

export function useBlender() {
    const dispatch = useAppDispatch();
    const blender = useAppSelector(selectBlender);
    const effectiveBlenderExePath = useAppSelector(selectEffectiveBlenderExePath);

    useEffect(() => {
        if (blender.detectedBlenderExePath === null && !blender.isDetecting) {
            void dispatch(detectBlender());
        }
    }, [dispatch, blender.detectedBlenderExePath, blender.isDetecting]);

    const redetectBlender = useCallback(() => {
        void dispatch(detectBlender());
    }, [dispatch]);

    const setBlenderExePath = useCallback(
        (path: string | null) => {
            dispatch(blenderExePathChanged(path));
        },
        [dispatch]
    );

    const clearBlenderExePath = useCallback(() => {
        dispatch(blenderExePathCleared());
    }, [dispatch]);

    const setExportToBlenderEnabled = useCallback(
        (enabled: boolean) => {
            dispatch(exportToBlenderToggled(enabled));
        },
        [dispatch]
    );

    const setAutoOpenBlendFile = useCallback(
        (enabled: boolean) => {
            dispatch(autoOpenBlendFileToggled(enabled));
        },
        [dispatch]
    );

    const triggerBlenderExport = useCallback(
        (recordingFolderPath?: string) => {
            return dispatch(
                exportRecordingToBlender(
                    recordingFolderPath ? {recordingFolderPath} : undefined
                )
            );
        },
        [dispatch]
    );

    const clearError = useCallback(() => {
        dispatch(blenderErrorCleared());
    }, [dispatch]);

    return {
        blenderExePath: blender.blenderExePath,
        detectedBlenderExePath: blender.detectedBlenderExePath,
        effectiveBlenderExePath,
        exportToBlenderEnabled: blender.exportToBlenderEnabled,
        autoOpenBlendFile: blender.autoOpenBlendFile,
        isExporting: blender.isExporting,
        isDetecting: blender.isDetecting,
        lastBlendFilePath: blender.lastBlendFilePath,
        error: blender.error,
        isUsingManualBlenderPath: blender.blenderExePath !== null,
        redetectBlender,
        setBlenderExePath,
        clearBlenderExePath,
        setExportToBlenderEnabled,
        setAutoOpenBlendFile,
        triggerBlenderExport,
        clearError,
    };
}
