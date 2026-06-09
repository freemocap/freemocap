import React, {useCallback, useMemo, useState} from 'react';
import {useLocation} from 'react-router-dom';
import {useTranslation} from 'react-i18next';
import IconButton from '@/components/ui-components/IconButton';
import {
    closestCenter,
    DndContext,
    DragEndEvent,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
} from '@dnd-kit/core';
import {arrayMove, SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy,} from '@dnd-kit/sortable';
import {restrictToParentElement, restrictToVerticalAxis} from '@dnd-kit/modifiers';


import {SortableSectionWrapper} from '@/components/common/SortableSectionWrapper';
import {CameraConfigTreeView} from '@/components/control-panels/camera-config-panel/camera-config-tree-view/CameraConfigTreeView';
import {RecordingInfoPanel} from "@/components/control-panels/recording-info-panel/RecordingInfoPanel";
import {RealtimePipelinePanel} from "@/components/control-panels/realtime-panel/RealtimePipelinePanel";
import {MocapPanel} from "@/components/control-panels/mocap-control-panel/MocapPanel";
import {CalibrationPanel} from "@/components/control-panels/calibration-control-panel/CalibrationPanel";
import {ServerConnectionStatus} from "@/components/control-panels/server-connection";
import {RecordingBrowserSection} from "@/components/playback/RecordingBrowserSection";


const STORAGE_KEY = 'freemocap-sidebar-section-order';

const DEFAULT_SECTION_ORDER = [
    'cameras',
    'recording',
    'realtime',
    'calibration',
    'mocap',
    'recordings',
] as const;

type SectionId = (typeof DEFAULT_SECTION_ORDER)[number];

const STREAMING_ONLY_SECTIONS = new Set<SectionId>(['cameras', 'recording']);
const PLAYBACK_ONLY_SECTIONS = new Set<SectionId>(['recordings']);

const SECTION_COMPONENTS: Record<SectionId, React.FC> = {
    realtime: RealtimePipelinePanel,
    cameras: CameraConfigTreeView,
    recording: RecordingInfoPanel,
    calibration: CalibrationPanel,
    mocap: MocapPanel,
    recordings: RecordingBrowserSection,
};

function loadSectionOrder(): SectionId[] {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (!stored) return [...DEFAULT_SECTION_ORDER];
        const parsed = JSON.parse(stored) as string[];
        const defaultSet = new Set<string>(DEFAULT_SECTION_ORDER);
        const parsedSet = new Set(parsed);
        if (
            parsed.length !== DEFAULT_SECTION_ORDER.length ||
            !parsed.every((id) => defaultSet.has(id)) ||
            !DEFAULT_SECTION_ORDER.every((id) => parsedSet.has(id))
        ) {
            return [...DEFAULT_SECTION_ORDER];
        }
        return parsed as SectionId[];
    } catch {
        return [...DEFAULT_SECTION_ORDER];
    }
}

function saveSectionOrder(order: SectionId[]): void {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(order));
    } catch {
        // Storage unavailable — ignore
    }
}

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
    const [sectionOrder, setSectionOrder] = useState<SectionId[]>(loadSectionOrder);

    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
    );

    const handleDragEnd = useCallback((event: DragEndEvent) => {
        const { active, over } = event;
        if (!over || active.id === over.id) return;
        setSectionOrder((prev) => {
            const oldIndex = prev.indexOf(active.id as SectionId);
            const newIndex = prev.indexOf(over.id as SectionId);
            const newOrder = arrayMove(prev, oldIndex, newIndex);
            saveSectionOrder(newOrder);
            return newOrder;
        });
    }, []);

    const modifiers = useMemo(() => [restrictToVerticalAxis, restrictToParentElement], []);

    const { pathname } = useLocation();
    const isStreaming = pathname === '/streaming';
    const isPlayback = pathname === '/playback';
    const visibleSections = useMemo(
        () => sectionOrder.filter(id =>
            (isStreaming || !STREAMING_ONLY_SECTIONS.has(id)) &&
            (isPlayback || !PLAYBACK_ONLY_SECTIONS.has(id))
        ),
        [sectionOrder, isStreaming, isPlayback],
    );

    const { t } = useTranslation();

    return (
        <>
            {isCollapsed && onToggleCollapse && (
                <CollapsedToolbar onToggleCollapse={onToggleCollapse} />
            )}

            <div className="inner flex gap-1 flex-col bg-darkgray br-2 w-full h-full"
                style={{ display: isCollapsed ? 'none' : 'flex' }}>
                {/* Header — home + connection + collapse button */}
                <div className="flex flex-row items-center gap-1 p-1" style={{ minHeight: 40 }}>
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
                        className="flex-1 overflow-hidden"
                        style={{ minWidth: 0 }}
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
                            className="icon-size-28"
                        />
                    )}
                </div>

                {/* Sidebar Sections — drag-reorderable */}
                <DndContext
                    sensors={sensors}
                    collisionDetection={closestCenter}
                    modifiers={modifiers}
                    onDragEnd={handleDragEnd}
                >
                    <SortableContext items={visibleSections} strategy={verticalListSortingStrategy}>
                        <div className="flex flex-col gap-1 p-1" style={{ paddingBottom: 16 }}>
                            {visibleSections.map((sectionId) => {
                                const Component = SECTION_COMPONENTS[sectionId];
                                return (
                                    <SortableSectionWrapper key={sectionId} id={sectionId}>
                                        <Component />
                                    </SortableSectionWrapper>
                                );
                            })}
                        </div>
                    </SortableContext>
                </DndContext>
            </div>
        </>
    );
};
