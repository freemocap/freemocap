import React, { useEffect, useCallback, useState } from 'react';
import { useAppDispatch, useAppSelector, selectCameras, selectConnectedCameras, selectIsLoading, detectCameras } from '@/store';
import { camerasConnectOrUpdate, pauseUnpauseCameras, closeCameras } from '@/store/slices/cameras/cameras-thunks';
import { savedSettingsCleared } from '@/store/slices/cameras/cameras-slice';
import { selectIsPaused } from '@/store/slices/cameras/cameras-selectors';
import { CameraTreeItem } from './CameraTreeItem';
import { NoCamerasPlaceholder } from './NoCamerasPlaceholder';
import { useServer } from '@/services/server/ServerContextProvider';
import { useTranslation } from 'react-i18next';
import ButtonSm from '@/components/ui-components/ButtonSm';
import IconButton from "@/components/ui-components/IconButton";
import { useRecordingGuard } from '@/components/RecordingGuardProvider';


export const CameraConfigSidebarPanel: React.FC = () => {
    const [isStoppingCameras, setIsStoppingCameras] = useState(false);
    const dispatch = useAppDispatch();
    const { isConnected } = useServer();
    const { t } = useTranslation();
    const { requestGuardedAction } = useRecordingGuard();
    const cameras = useAppSelector(selectCameras);
    const connectedCameras = useAppSelector(selectConnectedCameras);
    const isLoading = useAppSelector(selectIsLoading);
    const isPaused = useAppSelector(selectIsPaused);
    const isRecording = useAppSelector((state) => state.recording.isRecording);

    useEffect(() => {
        if (isConnected && cameras.length === 0) {
            dispatch(detectCameras({ filterVirtual: true }));
        }
    }, [isConnected, cameras.length, dispatch]);

    useEffect(() => {
        if (isStoppingCameras && connectedCameras.length === 0) {
            setIsStoppingCameras(false);
        }
    }, [isStoppingCameras, connectedCameras.length]);

    const handleUpdate = useCallback(() => {
        requestGuardedAction('Stop Recording & Update Camera Config', () => dispatch(camerasConnectOrUpdate()));
    }, [dispatch, requestGuardedAction]);

    const handleDetect = useCallback(() => {
        requestGuardedAction('Stop Recording & Detect Cameras', () => dispatch(detectCameras({ filterVirtual: true })));
    }, [dispatch, requestGuardedAction]);

    const handleStop = useCallback(() => {
        requestGuardedAction('Stop Recording & Close Cameras', () => {
            setIsStoppingCameras(true);
            dispatch(closeCameras());
        });
    }, [dispatch, requestGuardedAction]);

    return (
        <div className="camera-config-sidebar-panel flex flex-col flex-1 bg-middark br-2 p-1 min-h-0">
            {/* Header */}
            <div className="camera-group-header flex flex-row flex-wrap items-center gap-1 p-1 pos-rel z-2">
                {/* Row 1 — actions */}
              
               
                    
                     
                                                <p className="flex flex-row text md text-gray">{cameras.length} Cameras</p>
                            {connectedCameras.length > 0 && (
                                <span
                                    className="text md"
                                    style={{ color: 'var(--color-success, #4ade80)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                                >
                                    {/* <span className="icon icon-size-20 streaming-icon" /> */}
                                    {connectedCameras.length} Streaming
                                </span>
                            )}
                    <div className="flex-1" />
                    {/* Buttons: Detect + Connect OR Pause/Stop (when connected) */}
                    <div data-onboarding="connect-cameras" className="button-group flex items-center gap-1 pos-rel">
                           
                           
                        
                     
                     <IconButton
                        icon="scan-icon"
                        onClick={handleDetect}
                        tooltip={true}
                        tooltipText={isRecording ? t('stopRecordingFirst') : "Detect new cameras"}
                        tooltipPosition="pos-bottom"
                        disabled={isRecording}
                    />
                        {connectedCameras.length === 0 ? (
                            <ButtonSm
                              text={isLoading ? 'Connecting...' : 'Connect Cameras'}
                              iconClass={isLoading ? 'loader-icon' : 'stream-icon'}
                              onClick={handleUpdate}
                              textColor = "text-black"
                              className={isLoading ? 'disabled primary' : 'primary'}
                              
                            tooltip={true}
                            tooltipText="Connect to Cameras"
                            tooltipPosition="pos-bottom-right"

                            />
                        ) : (
                            <>
                                <IconButton
                                    icon={isPaused ? 'play-icon' : 'pause-icon'}
                                    onClick={() => requestGuardedAction('Stop Recording & Pause Cameras', () => dispatch(pauseUnpauseCameras()))}
                                    tooltip={true}
                                    tooltipText={isRecording ? t('stopRecordingFirst') : isPaused ? t('resumeStreaming') : t('pauseStreaming')}
                                    tooltipPosition="pos-bottom-right"
                                    disabled={isRecording}
                                />
                                <IconButton
                                    icon={isStoppingCameras ? 'loader-icon' : 'stopstreaming-icon'}
                                    onClick={handleStop}
                                    tooltip={true}
                                    tooltipText={isRecording ? t('stopRecordingFirst') : t('closeAllCameras')}
                                    tooltipPosition="pos-bottom-right"
                                    disabled={isRecording || isStoppingCameras}
                                />
                            </>
                        )}
                    </div>
               
            </div>

            {/* Camera list */}
            <div className="camera-list-container flex flex-col overflow-y z-1 pos-rel">
                {cameras.length === 0 ? (
                    <NoCamerasPlaceholder />
                ) : (
                    cameras
                        .slice()
                        .sort((a, b) => a.index - b.index)
                        .map(camera => (
                            <CameraTreeItem key={camera.id} camera={camera} />
                        ))
                )}
            </div>
        </div>
    );
};
