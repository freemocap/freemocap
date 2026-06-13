import React, {useCallback, useEffect, useState} from "react";

import {useAppDispatch, useAppSelector} from "@/store";
import {
    camerasConnectOrUpdate,
    closeCameras,
    detectCameras,
    pauseUnpauseCameras,
} from "@/store/slices/cameras/cameras-thunks";
import {selectConnectedCameras, selectIsLoading, selectIsPaused} from "@/store/slices/cameras";
import {useTranslation} from 'react-i18next';
import IconButton from "@/components/ui-components/IconButton";
import ButtonSm from "@/components/ui-components/ButtonSm";

export const CameraHeaderActions: React.FC = () => {
    const dispatch = useAppDispatch();
    const {t} = useTranslation();
    const [isStoppingCameras, setIsStoppingCameras] = useState(false);

    const isLoading = useAppSelector(selectIsLoading);
    const isPaused = useAppSelector(selectIsPaused);
    const connectedCameras = useAppSelector(selectConnectedCameras);
    const isRecording = useAppSelector(state => state.recording.isRecording);

    useEffect(() => {
        if (isStoppingCameras && connectedCameras.length === 0) {
            setIsStoppingCameras(false);
        }
    }, [isStoppingCameras, connectedCameras.length]);

    const handleDetect = useCallback(() => {
        dispatch(detectCameras({filterVirtual: true}));
    }, [dispatch]);

    const handleUpdate = useCallback(() => {
        dispatch(camerasConnectOrUpdate());
    }, [dispatch]);

    const handleStop = useCallback(() => {
        setIsStoppingCameras(true);
        dispatch(closeCameras());
    }, [dispatch]);

    const handlePauseUnpause = useCallback(() => {
        dispatch(pauseUnpauseCameras());
    }, [dispatch]);

    return (
        <>
            <IconButton
                icon="scan-icon"
                onClick={handleDetect}
                tooltip
                tooltipText={isRecording ? t('stopRecordingFirst') : t('detectCameras')}
                tooltipPosition="pos-bottom"
                disabled={isRecording}
            />

            {connectedCameras.length === 0 ? (
                <ButtonSm
                    text={isLoading ? t('connecting') : t('connectCameras')}
                    iconClass={isLoading ? '' : ''}
                    onClick={handleUpdate}
                    textColor="text-black"
                    className={isLoading ? 'disabled primary' : 'secondary'}
                    tooltip
                    tooltipText={t('connectCameras')}
                    tooltipPosition="pos-bottom-right"
                />
            ) : (
                <>
                    <IconButton
                        icon={isPaused ? 'play-icon' : 'pause-icon'}
                        onClick={handlePauseUnpause}
                        tooltip
                        tooltipText={isRecording ? t('stopRecordingFirst') : isPaused ? t('resumeStreaming') : t('pauseStreaming')}
                        tooltipPosition="pos-bottom-right"
                        disabled={isRecording}
                    />
                    <IconButton
                        icon={isStoppingCameras ? 'loader-icon' : 'stopstreaming-icon'}
                        onClick={handleStop}
                        tooltip
                        tooltipText={isRecording ? t('stopRecordingFirst') : t('closeAllCameras')}
                        tooltipPosition="pos-bottom-right"
                        disabled={isRecording || isStoppingCameras}
                    />
                </>
            )}
        </>
    );
};
