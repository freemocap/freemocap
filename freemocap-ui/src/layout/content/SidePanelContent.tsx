import React, {useCallback, useMemo, useState} from 'react';
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
import {useNavigate} from 'react-router-dom';

import {SortableSectionWrapper} from '@/components/common/SortableSectionWrapper';
import {CameraConfigTreeView} from '@/components/control-panels/camera-config-panel/camera-config-tree-view/CameraConfigTreeView';
import {RecordingInfoPanel} from "@/components/control-panels/recording-info-panel/RecordingInfoPanel";
import {RealtimePipelinePanel} from "@/components/control-panels/realtime-panel/RealtimePipelinePanel";
import {MocapPanel} from "@/components/control-panels/mocap-control-panel/MocapPanel";
import {CalibrationPanel} from "@/components/control-panels/calibration-control-panel/CalibrationPanel";
import {ServerConnectionStatus} from "@/components/control-panels/server-connection";

const STORAGE_KEY = 'freemocap-sidebar-section-order';

const DEFAULT_SECTION_ORDER = [
    'cameras',
    'recording',
    'realtime',
    'calibration',
    'mocap',
] as const;

type SectionId = (typeof DEFAULT_SECTION_ORDER)[number];

const SECTION_COMPONENTS: Record<SectionId, React.FC> = {
    realtime: RealtimePipelinePanel,
    cameras: CameraConfigTreeView,
    recording: RecordingInfoPanel,
    calibration: CalibrationPanel,
    mocap: MocapPanel,
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

export const SidePanelContent = () => {
    const navigate = useNavigate();
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

    return (
        <div className="w-full h-full flex flex-col overflow-y overflow-hidden">
            {/* Header */}
            <div className="flex flex-row items-center justify-content-space-between p-2" style={{ minHeight: 40, borderBottom: '1px solid var(--color-border-secondary)' }}>
                <span className="title text-white">FreeMoCap 💀✨</span>
                <div className="flex flex-row items-center gap-1">
                    <button
                        className="button icon-button br-1"
                        onClick={() => navigate('/streaming')}
                        title="Cameras"
                    >
                        <span className="icon streaming-icon icon-size-20" />
                    </button>
                </div>
            </div>

            <ServerConnectionStatus />

            {/* Sidebar Sections — drag-reorderable */}
            <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                modifiers={modifiers}
                onDragEnd={handleDragEnd}
            >
                <SortableContext items={sectionOrder} strategy={verticalListSortingStrategy}>
                    <div className="flex flex-col gap-1 p-1" style={{ paddingBottom: 16 }}>
                        {sectionOrder.map((sectionId) => {
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
    );
};
