import * as React from 'react';
import {useState} from "react";
import {useTranslation} from "react-i18next";
import {useLocation} from "react-router-dom";
import {useAppDispatch, useAppSelector} from "@/store";
import {startRecording, stopRecording} from "@/store";
import {useServer} from "@/services/server/ServerContextProvider";
import {RecordingInfoPanel} from "@/components/recording-info-panel/RecordingInfoPanel";
import {getTimestampString} from "@/components/recording-info-panel/getTimestampString";
import {ServerConnectionStatus} from "@/components/ServerConnectionStatus";
import {CameraConfigSidebarPanel} from "@/components/camera-config-tree-view/CameraConfigSidebarPanel";
import {PlaybackSidebarPanel} from "@/components/playback-sidebar/PlaybackSidebarPanel";
import ButtonSm from "@/components/ui-components/ButtonSm";
import IconButton from "@/components/ui-components/IconButton";

interface LeftSidePanelContentProps {
    isCollapsed: boolean;
    onToggleCollapse: () => void;
    onOpenWelcome?: () => void;
}

const CollapsedToolbar: React.FC<{
    onToggleCollapse: () => void;
    isRecording: boolean;
    noCameras: boolean;
    onRecordClick: () => void;
    onOpenWelcome?: () => void;
}> = ({onToggleCollapse, isRecording, noCameras, onRecordClick, onOpenWelcome}) => {
    const {t} = useTranslation();

    return (
        <div className="collapsed-sidebar items-center flex flex-col items-center w-full h-full pt-1 gap-1"       >
            <IconButton
                icon="expand-icon"
                onClick={onToggleCollapse}
                tooltip={true}
                tooltipText={t('expandSidebar')}
                tooltipPosition="pos-right"
            />

            {onOpenWelcome && (
                <IconButton
                    icon="home-icon"
                    onClick={onOpenWelcome}
                    tooltip={true}
                    tooltipText={t('home')}
                    tooltipPosition="pos-right"
                />
            )}

            <ServerConnectionStatus compact />
            
            <ButtonSm
                className={`collapsed-start-recording-btn record-button-sm ${isRecording ? 'record-button-active' : 'record-button-idle'}`}
                onClick={onRecordClick}
                disabled={noCameras && !isRecording}
                tooltip={true}
                tooltipText={isRecording ? t('stopRecording') : t('startRecording')}
                tooltipPosition="pos-right"
                iconClass={isRecording ? 'close-icon' : 'record-icon'}
                text=""
            />
        </div>
    );
};

export const LeftSidePanelContent: React.FC<LeftSidePanelContentProps> = ({isCollapsed, onToggleCollapse, onOpenWelcome}) => {
    const dispatch = useAppDispatch();
    const {t} = useTranslation();
    const location = useLocation();
    const isPlayback = location.pathname.startsWith('/playback');

    const recordingInfo = useAppSelector((state) => state.recording);
    const isRecording = recordingInfo.isRecording;
    const {connectedCameraIds} = useServer();
    const noCameras = connectedCameraIds.length === 0;
    const [micDeviceIndex] = useState<number>(-1);

    const handleCollapsedRecordClick = async (): Promise<void> => {
        if (isRecording) {
            await dispatch(stopRecording()).unwrap();
        } else {
            const recordingName = getTimestampString();
            await dispatch(startRecording({
                recordingName,
                recordingDirectory: recordingInfo.recordingDirectory,
                micDeviceIndex,
            })).unwrap();
        }
    };

    return (
        <>
            {isCollapsed && (
                <CollapsedToolbar
                    onToggleCollapse={onToggleCollapse}
                    isRecording={isRecording}
                    noCameras={noCameras}
                    onRecordClick={handleCollapsedRecordClick}
                    onOpenWelcome={onOpenWelcome}
                />
            )}

            {/* Always mounted — display:none preserves component state when collapsed */}
            <div
                className="inner flex gap-1 flex-col bg-darkgray br-2 w-full h-full"
                style={{ display: isCollapsed ? 'none' : 'flex' }}
            >
                {/* Header row */}
                <div
                    className="flex items-center gap-1 px-1 py-1"
                    // style={{
                    //     borderBottom: '1px solid var(--color-surface-active)',
                    //     minHeight: 40,
                    // }}
                >

                    {onOpenWelcome && (
                        <IconButton
                            icon="home-icon"
                            onClick={onOpenWelcome}
                            tooltip={true}
                            tooltipText={t('home')}
                            tooltipPosition="pos-right"
                        />
                    )}
                    <div
                    data-warning="service-unavailable"
                    className="flex-1 overflow-hidden" style={{minWidth: 0}}>
                        <ServerConnectionStatus />
                    </div>
                    <IconButton
                        icon="collapse-icon"
                        onClick={onToggleCollapse}
                        tooltip={true}
                        tooltipText={t('collapseSidebar')}
                        tooltipPosition="pos-left"
                        className="icon-size-25"
                    />
                </div>

                {/* Main content */}
                <div className="side-action-main-container h-full flex flex-col gap-1 flex-1 overflow-hidden">
                    {isPlayback ? (
                        <PlaybackSidebarPanel/>
                    ) : (
                        <>
                            <div className="flex-1 min-h-0 overflow-hidden">
                                <CameraConfigSidebarPanel/>
                            </div>
                            <RecordingInfoPanel/>
                        </>
                    )}
                </div>
            </div>
        </>
    );
};
