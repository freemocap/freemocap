import React, {useCallback, useLayoutEffect, useMemo, useRef, useState} from 'react';
import {useLocation} from 'react-router-dom';
import {useTranslation} from 'react-i18next';
import {ImperativePanelGroupHandle, Panel, PanelGroup, PanelResizeHandle} from 'react-resizable-panels';
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
    // 'mocap',
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

// Sections that are meant to grow and scroll internally (their content is
// open-ended). They get a small fixed floor; every other section's floor is
// measured from its own content so it can never be squashed (see useContentMinSizes).
const GROWABLE_SECTIONS = new Set<SectionId>(['cameras', 'recordings']);

// Pixel height of each resize divider (must match `.resizable-component` in components.css).
const HANDLE_PX = 10;
// Floor for growable sections — they scroll internally, so they may shrink freely.
const GROWABLE_MIN_PCT = 8;
// A single content section may not demand more than this share as its minimum,
// so one tall section can never lock out everything else.
const CONTENT_MIN_CAP_PCT = 70;

// Build a panel layout (percentages that sum to 100) in which every non-growable
// section sits at its floor — its measured content height as a percentage
// (`minById[id]`), or GROWABLE_MIN_PCT before measurement — and the growable
// section(s) absorb ALL remaining space. This is the "cameras maximized, nothing
// crushed below its content" layout, used both as the first-paint default and as
// the layout we imperatively re-assert once content has been measured.
const computeLayout = (
    sections: readonly SectionId[],
    minById: Partial<Record<SectionId, number>>,
): number[] => {
    const growableCount = sections.filter(id => GROWABLE_SECTIONS.has(id)).length;

    if (growableCount === 0) {
        const each = 100 / sections.length;
        return sections.map(() => each);
    }

    const nonGrowableFloor = (id: SectionId): number => minById[id] ?? GROWABLE_MIN_PCT;
    const nonGrowableTotal = sections
        .filter(id => !GROWABLE_SECTIONS.has(id))
        .reduce((sum, id) => sum + nonGrowableFloor(id), 0);
    const growableEach = (100 - nonGrowableTotal) / growableCount;

    return sections.map(id =>
        GROWABLE_SECTIONS.has(id) ? growableEach : nonGrowableFloor(id),
    );
};

/**
 * Measures each non-growable section's natural content height and expresses it as
 * a percentage of the panel group, fed back to react-resizable-panels as that
 * panel's `minSize`. This makes the minimum size of a section track its content,
 * so a section can never be dragged smaller than what it contains (which would
 * otherwise clip its content and bleed it onto the neighbouring section).
 */
function useContentMinSizes(sections: readonly SectionId[]) {
    const groupElRef = useRef<HTMLDivElement | null>(null);
    const contentEls = useRef<Map<SectionId, HTMLElement>>(new Map());
    const observerRef = useRef<ResizeObserver | null>(null);
    const refCbCache = useRef<Map<SectionId, (el: HTMLElement | null) => void>>(new Map());
    const [minPctById, setMinPctById] = useState<Partial<Record<SectionId, number>>>({});

    const recompute = useCallback(() => {
        const groupEl = groupElRef.current;
        if (!groupEl) return;
        const available = Math.max(1, groupEl.clientHeight - (sections.length - 1) * HANDLE_PX);
        const next: Partial<Record<SectionId, number>> = {};
        for (const id of sections) {
            if (GROWABLE_SECTIONS.has(id)) {
                next[id] = GROWABLE_MIN_PCT;
                continue;
            }
            const el = contentEls.current.get(id);
            const contentPx = el ? el.scrollHeight : 0;
            next[id] = Math.min(CONTENT_MIN_CAP_PCT, Math.max(3, (contentPx / available) * 100));
        }
        setMinPctById((prev) => {
            const unchanged = sections.every(
                (id) => Math.abs((prev[id] ?? -1) - (next[id] ?? -1)) < 0.5,
            );
            return unchanged ? prev : next;
        });
    }, [sections]);

    // Single observer watching the group and every measured content element.
    // useLayoutEffect runs after refs are attached but before paint, so the first
    // frame already has correct minimums (no squash flash).
    useLayoutEffect(() => {
        const observer = new ResizeObserver(() => recompute());
        observerRef.current = observer;
        if (groupElRef.current) observer.observe(groupElRef.current);
        contentEls.current.forEach((el) => observer.observe(el));
        recompute();
        return () => {
            observer.disconnect();
            observerRef.current = null;
        };
    }, [recompute]);

    const setGroupEl = useCallback((el: HTMLDivElement | null) => {
        groupElRef.current = el;
        if (el) observerRef.current?.observe(el);
    }, []);

    const registerContent = useCallback((id: SectionId) => {
        let cb = refCbCache.current.get(id);
        if (!cb) {
            cb = (el: HTMLElement | null) => {
                const prev = contentEls.current.get(id);
                if (prev) observerRef.current?.unobserve(prev);
                if (el) {
                    contentEls.current.set(id, el);
                    observerRef.current?.observe(el);
                } else {
                    contentEls.current.delete(id);
                }
            };
            refCbCache.current.set(id, cb);
        }
        return cb;
    }, []);

    return {setGroupEl, registerContent, minPctById};
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

    const defaultSizes = useMemo(() => computeLayout(visibleSections, {}), [visibleSections]);
    const { setGroupEl, registerContent, minPctById } = useContentMinSizes(visibleSections);

    const panelGroupRef = useRef<ImperativePanelGroupHandle>(null);
    const userResizedRef = useRef(false);
    const layoutKey = visibleSections.join('|');

    // A new set of sections (route change) gets a fresh maximized default — the
    // user hasn't expressed a preference for it yet.
    useLayoutEffect(() => {
        userResizedRef.current = false;
    }, [layoutKey]);

    // Keep cameras maximized (every other section at its measured content floor)
    // until the user drags a divider. This must be imperative: the panel library
    // applies defaultSize once at mount, then re-clamps the *current* layout when
    // the measured minSizes arrive on a later render, permanently stealing that
    // space back from cameras. Re-asserting on every floor change (rather than
    // once) also survives the startup window resize (launch → maximize), which
    // would otherwise leave cameras stuck at the small-window proportions.
    useLayoutEffect(() => {
        if (userResizedRef.current) return;
        const allFloorsMeasured = visibleSections.every(
            id => GROWABLE_SECTIONS.has(id) || minPctById[id] != null,
        );
        if (!allFloorsMeasured) return;
        panelGroupRef.current?.setLayout(computeLayout(visibleSections, minPctById));
    }, [visibleSections, minPctById]);

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
                        data-onboarding="connection:server-connection"
                        className="server-connection-container flex-1 overflow-hidden min-w-0"
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

                {/* Sidebar Sections — vertically resizable (react-resizable-panels).
                    Each section's minimum size is measured from its content so it can
                    never be squashed below what it contains. */}
                <div ref={setGroupEl} className="flex-1 min-h-0">
                    <PanelGroup
                        ref={panelGroupRef}
                        key={visibleSections.join('|')}
                        direction="vertical"
                        className="h-full gap-1"
                    >
                        {visibleSections.map((id, index) => {
                            const Component = SECTION_COMPONENTS[id];
                            const growable = GROWABLE_SECTIONS.has(id);
                            const minSize = minPctById[id] ?? (growable ? GROWABLE_MIN_PCT : 4);
                            return (
                                <React.Fragment key={id}>
                                    {index > 0 && index < visibleSections.length - 1 && (
                                        <PanelResizeHandle
                                            className="resizable-component"
                                            onDragging={(isDragging) => {
                                                if (isDragging) userResizedRef.current = true;
                                            }}
                                        />
                                    )}
                                    {/* Insert new resize handle between recording_path and recording_control */}
                                    {index === 3 && (
                                        <PanelResizeHandle
                                            className="resizable-component"
                                            onDragging={(isDragging) => {
                                                if (isDragging) userResizedRef.current = true;
                                            }}
                                        />
                                    )}
                                    <Panel
                                        id={id}
                                        order={index}
                                        defaultSize={Math.max(defaultSizes[index], minSize)}
                                        minSize={minSize}
                                        
                                    >
                                        {growable ? (
                                            <div className="h-full min-h-0 flex flex-col">
                                                <Component />
                                            </div>
                                        ) : (
                                            <div className="mocap-inner-section h-full min-h-0 overflow-y">
                                                <div ref={registerContent(id)} className="flex flex-col">
                                                    <Component />
                                                </div>
                                            </div>
                                        )}
                                    </Panel>
                                </React.Fragment>
                            );
                        })}
                    </PanelGroup>
                </div>
            </div>
        </>
    );
};
