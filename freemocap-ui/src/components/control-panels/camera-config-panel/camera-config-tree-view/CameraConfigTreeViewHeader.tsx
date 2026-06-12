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
import IconButton from "@/components/ui-components/IconButton";

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
                <IconButton
                    icon={isAutoApply ? "sync-icon" : "sync-disabled-icon"}
                    onClick={() => dispatch(autoApplyToggled())}
                    title={isAutoApply ? 'Auto-apply on — changes send automatically' : 'Auto-apply off — use apply button to send'}
                    style={{
                        color: isAutoApply ? 'var(--color-accent)' : 'inherit',
                        opacity: isAutoApply ? 1 : 0.5,
                    }}
                />

                <IconButton
                    icon="videocam-icon"
                    className="icon-size-25 br-2 p-1"
                    onClick={handleConnectOrApply}
                    title={t("connectCameras")}
                    style={{
                        color: 'var(--color-accent)',
                        border: '2px solid var(--color-accent)',
                    }}
                    iconStyle={{color: 'var(--color-accent)'}}
                />

                <IconButton
                    icon={isPaused ? "play-icon" : "pause-icon"}
                    onClick={handlePauseUnpause}
                    title={isPaused ? t("resumeStreaming") : t("pauseStreaming")}
                />

                <IconButton
                    icon="videocam-off-icon"
                    onClick={handleCloseCameras}
                    title={t("closeAllCameras")}
                />

                <IconButton
                    icon={isLoading || isActionInProgress ? "loader-icon" : "refresh-icon"}
                    onClick={handleRefreshCameras}
                    title={t("detectCameras")}
                />

                <IconButton
                    icon="clear-icon"
                    onClick={handleClearSavedSettings}
                    title={t("clearCameraSettings")}
                />
            </div>
        </div>
    );
};
