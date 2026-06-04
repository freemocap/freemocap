import React, {useState} from "react";

import {useAppDispatch} from "@/store";
import {
    camerasConnectOrUpdate,
    closeCameras,
    detectCameras,
    pauseUnpauseCameras,
} from "@/store/slices/cameras/cameras-thunks";
import {savedSettingsCleared} from "@/store/slices/cameras/cameras-slice";
import {useTranslation} from 'react-i18next';
import IconButton from "@/components/ui-components/IconButton";

interface CameraHeaderActionsProps {
    isLoading: boolean;
    isPaused: boolean;
}

export const CameraHeaderActions: React.FC<CameraHeaderActionsProps> = ({
    isLoading,
    isPaused,
}) => {
    const dispatch = useAppDispatch();
    const {t} = useTranslation();

    const [isActionInProgress, setIsActionInProgress] = useState(false);

    const handleRefreshCameras = async (): Promise<void> => {
        setIsActionInProgress(true);
        try {
            await dispatch(detectCameras({filterVirtual: true})).unwrap();
        } catch (error) {
            console.error('Error detecting cameras:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handleConnectOrApply = async (): Promise<void> => {
        setIsActionInProgress(true);
        try {
            await dispatch(camerasConnectOrUpdate()).unwrap();
        } catch (error) {
            console.error('Error with camera operation:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handleCloseCameras = async (): Promise<void> => {
        setIsActionInProgress(true);
        try {
            await dispatch(closeCameras()).unwrap();
        } catch (error) {
            console.error('Error closing cameras:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handlePauseUnpause = async (): Promise<void> => {
        setIsActionInProgress(true);
        try {
            await dispatch(pauseUnpauseCameras()).unwrap();
        } catch (error) {
            console.error('Error pausing/unpausing cameras:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handleClearSavedSettings = (): void => {
        dispatch(savedSettingsCleared());
    };

    const busy = isLoading || isActionInProgress;

    return (
        <>
            <IconButton
                icon="stream-icon"
                onClick={handleConnectOrApply}
                title={t("connectCameras")}
                tooltip
                tooltipText={t("connectCameras")}
                tooltipPosition="pos-bottom-right"
            />

            <IconButton
                icon={isPaused ? "play-icon" : "pause-icon"}
                onClick={handlePauseUnpause}
                title={isPaused ? t("resumeStreaming") : t("pauseStreaming")}
                tooltip
                tooltipText={isPaused ? t("resumeStreaming") : t("pauseStreaming")}
                tooltipPosition="pos-bottom"
            />

            <IconButton
                icon="stopstreaming-icon"
                onClick={handleCloseCameras}
                title={t("closeAllCameras")}
                tooltip
                tooltipText={t("closeAllCameras")}
                tooltipPosition="pos-bottom"
            />

            <IconButton
                icon={busy ? "loader-icon" : "rotate-icon"}
                onClick={handleRefreshCameras}
                title={t("detectCameras")}
                tooltip
                tooltipText={t("detectCameras")}
                tooltipPosition="pos-bottom"
            />

            <IconButton
                icon="clear-icon"
                onClick={handleClearSavedSettings}
                title={t("clearCameraSettings")}
                tooltip
                tooltipText={t("clearCameraSettings")}
                tooltipPosition="pos-bottom"
            />
        </>
    );
};
