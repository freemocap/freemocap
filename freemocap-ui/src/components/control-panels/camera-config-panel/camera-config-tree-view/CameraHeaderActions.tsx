import React, {useState} from "react";

import {useAppDispatch} from "@/store";
import {
    camerasConnectOrUpdate,
    closeCameras,
    detectCameras,
    pauseUnpauseCameras,
} from "@/store/slices/cameras/cameras-thunks";
import {recommendExposureForAll, savedSettingsCleared} from "@/store/slices/cameras/cameras-slice";
import {useTranslation} from 'react-i18next';

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

    const handleRefreshCameras = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();
        setIsActionInProgress(true);
        try {
            await dispatch(detectCameras({filterVirtual: true})).unwrap();
        } catch (error) {
            console.error('Error detecting cameras:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handleConnectOrApply = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();
        setIsActionInProgress(true);
        try {
            await dispatch(camerasConnectOrUpdate()).unwrap();
        } catch (error) {
            console.error('Error with camera operation:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handleCloseCameras = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();
        setIsActionInProgress(true);
        try {
            await dispatch(closeCameras()).unwrap();
        } catch (error) {
            console.error('Error closing cameras:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handlePauseUnpause = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();
        setIsActionInProgress(true);
        try {
            await dispatch(pauseUnpauseCameras()).unwrap();
        } catch (error) {
            console.error('Error pausing/unpausing cameras:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handleRecommendExposureAll = (e: React.MouseEvent): void => {
        e.stopPropagation();
        dispatch(recommendExposureForAll());
    };

    const handleClearSavedSettings = (e: React.MouseEvent): void => {
        e.stopPropagation();
        dispatch(savedSettingsCleared());
    };

    const busy = isLoading || isActionInProgress;

    return (
        <>
            <button
                className="button icon-button br-1"
                onClick={handleConnectOrApply}
                title={t("connectCameras")}
                style={{
                    padding: "4px",
                    color: 'var(--color-accent)',
                    border: '2px solid var(--color-accent)',
                    borderRadius: 8,
                }}
            >
                <span className="icon videocam-icon icon-size-20" style={{position: 'relative', display: 'inline-flex', width: 28, height: 28}} />
            </button>

            <button
                className="button icon-button br-1"
                onClick={handleRecommendExposureAll}
                title="Auto-recommend exposure for all cameras"
                style={{padding: "4px"}}
            >
                <span className="icon bulb-icon icon-size-20" />
            </button>

            <button
                className="button icon-button br-1"
                onClick={handlePauseUnpause}
                title={isPaused ? t("resumeStreaming") : t("pauseStreaming")}
                style={{padding: "4px"}}
            >
                {isPaused
                    ? <span className="icon play-icon icon-size-20" />
                    : <span className="icon pause-icon icon-size-20" />
                }
            </button>

            <button
                className="button icon-button br-1"
                onClick={handleCloseCameras}
                title={t("closeAllCameras")}
                style={{padding: "4px"}}
            >
                <span className="icon videocam-off-icon icon-size-20" />
            </button>

            <button
                className="button icon-button br-1"
                onClick={handleRefreshCameras}
                title={t("detectCameras")}
                style={{padding: "4px"}}
            >
                {busy
                    ? <span className="icon loader-icon icon-size-20" />
                    : <span className="icon refresh-icon icon-size-20" />
                }
            </button>

            <button
                className="button icon-button br-1"
                onClick={handleClearSavedSettings}
                title={t("clearCameraSettings")}
                style={{padding: "4px"}}
            >
                <span className="icon clear-icon icon-size-20" />
            </button>
        </>
    );
};
