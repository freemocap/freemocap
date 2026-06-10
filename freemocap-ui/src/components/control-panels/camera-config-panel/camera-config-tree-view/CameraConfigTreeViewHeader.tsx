import React from "react";

import {useAppDispatch, useAppSelector} from "@/store";
import {
    camerasConnectOrUpdate,
    closeCameras,
    detectCameras,
    pauseUnpauseCameras,
} from "@/store/slices/cameras/cameras-thunks";
import {autoApplyToggled, savedSettingsCleared} from "@/store/slices/cameras/cameras-slice";
import {selectAutoApply} from "@/store/slices/cameras/cameras-selectors";
import {useTranslation} from 'react-i18next';

interface CameraConfigTreeViewHeaderProps {
    cameraCount: number;
    isLoading: boolean;
    isPaused: boolean;
}

export const CameraConfigTreeViewHeader: React.FC<CameraConfigTreeViewHeaderProps> = ({
    cameraCount,
    isLoading,
    isPaused,
}) => {
    const dispatch = useAppDispatch();
    const {t} = useTranslation();
    const isAutoApply = useAppSelector(selectAutoApply);
    const [isActionInProgress, setIsActionInProgress] = React.useState(false);

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
            console.log('Closed all cameras');
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

    const handleClearSavedSettings = (e: React.MouseEvent): void => {
        e.stopPropagation();
        dispatch(savedSettingsCleared());
    };

    const handleHeaderClick = (e: React.MouseEvent): void => {
        e.stopPropagation();
    };

    return (
        <div
            onClick={handleHeaderClick}
            className="flex flex-row items-center p-1 pt-2 pb-2"
            style={{
                backgroundColor: 'var(--color-bg-elevated)',
                color: '#fff',
            }}
        >
            <span className="icon videocam-icon icon-size-20 ml-2 mr-1" />
            <p className="text bg text-white flex-1">
                {t('camerasCount', {count: cameraCount})}
            </p>

            <div className="flex flex-row items-center gap-1 mr-2">
                <button
                    className="button icon-button br-1"
                    onClick={() => dispatch(autoApplyToggled())}
                    title={isAutoApply ? 'Auto-apply on — changes send automatically' : 'Auto-apply off — use apply button to send'}
                    style={{
                        color: isAutoApply ? 'var(--color-accent)' : 'inherit',
                        opacity: isAutoApply ? 1 : 0.5,
                    }}
                >
                    {isAutoApply
                        ? <span className="icon sync-icon icon-size-20" />
                        : <span className="icon sync-disabled-icon icon-size-20" />
                    }
                </button>

                <button
                    className="button icon-button br-2 p-1"
                    onClick={handleConnectOrApply}
                    title={t("connectCameras")}
                    style={{
                        color: 'var(--color-accent)',
                        border: '2px solid var(--color-accent)',
                    }}
                >
                    <span className="pos-rel flex-inline" style={{width: 28, height: 28}}>
                        <span className="icon videocam-icon icon-size-20" style={{color: 'var(--color-accent)'}} />
                        <span className="icon arrow-down-icon icon-size-12" style={{
                            position: 'absolute',
                            top: -6,
                            left: '50%',
                            transform: 'translateX(-50%)',
                            color: 'var(--color-accent)',
                            filter: 'drop-shadow(0 0 2px rgba(0,0,0,0.8))',
                        }} />
                    </span>
                </button>

                <button
                    className="button icon-button br-1"
                    onClick={handlePauseUnpause}
                    title={isPaused ? t("resumeStreaming") : t("pauseStreaming")}
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
                >
                    <span className="icon videocam-off-icon icon-size-20" />
                </button>

                <button
                    className="button icon-button br-1"
                    onClick={handleRefreshCameras}
                    title={t("detectCameras")}
                >
                    {isLoading || isActionInProgress
                        ? <span className="icon loader-icon icon-size-20" />
                        : <span className="icon refresh-icon icon-size-20" />
                    }
                </button>

                <button
                    className="button icon-button br-1"
                    onClick={handleClearSavedSettings}
                    title={t("clearCameraSettings")}
                >
                    <span className="icon clear-icon icon-size-20" />
                </button>
            </div>
        </div>
    );
};
