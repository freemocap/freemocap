import React, {useMemo} from 'react';
import {useLocation} from 'react-router-dom';
import {useTranslation} from 'react-i18next';
import IconButton from '@/components/ui-components/IconButton';

import {CameraConfigTreeView} from '@/components/control-panels/camera-config-panel/camera-config-tree-view/CameraConfigTreeView';
import {RecordingPathPanel} from "@/components/control-panels/recording-info-panel/RecordingPathPanel";
import {RecordingControlPanel} from "@/components/control-panels/recording-info-panel/RecordingControlPanel";
import {RecordingInfoPanel as ProcessMocapPanel} from "@/components/control-panels/recording-info-panel/ProcessMocapPanel";
import {MocapPanel} from "@/components/control-panels/mocap-control-panel/MocapPanel";
import {ServerConnectionStatus} from "@/components/control-panels/server-connection";
import {RecordingBrowserSection} from "@/components/playback/RecordingBrowserSection";
import CalibrationModule from "@/components/pipeline-progress/calibration-progress/calibration-module";

const SECTION_ORDER = [
    'recordings',
    'cameras',
    'calibration',
    'recording_path',
    'recording_control',
    'process_mocap',
    'mocap',
] as const;

type SectionId = (typeof SECTION_ORDER)[number];

const STREAMING_ONLY_SECTIONS = new Set<SectionId>(['cameras', 'recording_path', 'recording_control']);
const PLAYBACK_ONLY_SECTIONS = new Set<SectionId>(['recordings', 'process_mocap']);

const SECTION_COMPONENTS: Record<SectionId, React.FC> = {
    cameras: CameraConfigTreeView,
    calibration: CalibrationModule,
    process_mocap: ProcessMocapPanel,
    recording_path: RecordingPathPanel,
    recording_control: RecordingControlPanel,
    mocap: MocapPanel,
    recordings: RecordingBrowserSection,
};

interface SidePanelContentProps {
    isCollapsed?: boolean;
    onToggleCollapse?: () => void;
    onOpenWelcome?: () => void;
}

const CollapsedToolbar: React.FC<{ onToggleCollapse: () => void }> = ({ onToggleCollapse }) => {
    const { t } = useTranslation();
    return (
        <div className="collapsed-sidebar items-center flex flex-col items-center w-full h-full pt-1 gap-1">
            <IconButton
                icon="expand-icon"
                onClick={onToggleCollapse}
                tooltip={true}
                tooltipText={t('expandSidebar')}
                tooltipPosition="pos-right"
            />
            <ServerConnectionStatus compact />
        </div>
    );
};

export const SidePanelContent = ({ isCollapsed = false, onToggleCollapse, onOpenWelcome }: SidePanelContentProps) => {
    const { pathname } = useLocation();
    const isStreaming = pathname === '/streaming';
    const isPlayback = pathname === '/playback';
    const isActiveRecording = pathname === '/active-recording';
    const visibleSections = useMemo(
        () => SECTION_ORDER.filter(id =>
            (isStreaming || !STREAMING_ONLY_SECTIONS.has(id)) &&
            (isPlayback || isActiveRecording || !PLAYBACK_ONLY_SECTIONS.has(id))
        ),
        [isStreaming, isPlayback, isActiveRecording],
    );

    const { t } = useTranslation();

    return (
        <>
            {isCollapsed && onToggleCollapse && (
                <CollapsedToolbar onToggleCollapse={onToggleCollapse} />
            )}

            <div className="playback-mode left-side-panel flex gap-1 flex-col bg-darkgray br-2 w-full h-full"
                style={{ display: isCollapsed ? 'none' : 'flex' }}>
                {/* Header — home + connection + collapse button */}

                <div className="left-side-top-bar flex flex-row items-center gap-1 p-1"
                >
                    {onOpenWelcome && (
                        <IconButton
                            icon="home-icon"
                            onClick={onOpenWelcome}
                            tooltip={true}
                            tooltipText="Home"
                            tooltipPosition="pos-right"
                        />
                    )}
                    <div
                        data-warning="service-unavailable"
                        className="flex-1 overflow-hidden min-w-0"
                    >
                        <ServerConnectionStatus />
                    </div>
                    {onToggleCollapse && (
                        <IconButton
                            icon="collapse-icon"
                            onClick={onToggleCollapse}
                            tooltip={true}
                            tooltipText={t('collapseSidebar')}
                            tooltipPosition="pos-left"
                            className="icon-size-25"
                        />
                    )}
                </div>

                {/* Sidebar Sections */}
                <div className="playback-mode left-side-panel flex flex-col gap-1 min-h-0 h-full">
                    {visibleSections.map((sectionId) => {
                        const Component = SECTION_COMPONENTS[sectionId];
                        return <Component key={sectionId} />;
                    })}
                </div>
            </div>
        </>
    );
};
