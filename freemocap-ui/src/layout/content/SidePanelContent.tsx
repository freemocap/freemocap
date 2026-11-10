import {CalibrateRecordingButton} from '@/components/control-panels/calibration-actions/CalibrateRecordingButton';
import {useAppSelector} from '@/store';
import {selectActiveRecordingFullPath} from '@/store/slices/active-recording/active-recording-slice';
import React, {useCallback, useLayoutEffect, useMemo, useRef, useState} from 'react';
import {useLocation} from 'react-router-dom';
import {useTranslation} from 'react-i18next';
import {ImperativePanelGroupHandle, Panel, PanelGroup, PanelResizeHandle} from 'react-resizable-panels';
import IconButton from '@/components/ui-components/IconButton';
import {planSidebarSections} from '@/layout/content/sidebar-section-layout';

import {CameraConfigTreeView} from '@/components/control-panels/camera-config-panel/camera-config-tree-view/CameraConfigTreeView';
import {RecordingPathPanel} from "@/components/control-panels/recording-info-panel/RecordingPathPanel";
import {RecordingControlPanel} from "@/components/control-panels/recording-info-panel/RecordingControlPanel";
import {RecordingInfoPanel as ProcessMocapPanel} from "@/components/control-panels/recording-info-panel/ProcessMocapPanel";
import {ServerConnectionStatus} from "@/components/control-panels/server-connection";
import {RecordingBrowserSection} from "@/components/playback/RecordingBrowserSection";
import CalibrationModule from "@/components/pipeline-progress/calibration-progress/calibration-module";

function CalibrationPanel(): React.ReactElement {
    const location = useLocation();
    const recordingPath = useAppSelector(selectActiveRecordingFullPath);
    return <>
        {location.pathname === '/playback' && <CalibrateRecordingButton recordingPath={recordingPath}/>}
        <CalibrationModule/>
    </>;
}

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
    calibration: CalibrationPanel,
    process_mocap: ProcessMocapPanel,
    recording_path: RecordingPathPanel,
    recording_control: RecordingControlPanel,
    recordings: RecordingBrowserSection,
};

// Sections that are meant to grow and scroll internally (their content is
// open-ended). They keep a guaranteed floor and absorb all spare height; every
// other section prefers its measured content height (see sidebar-section-layout.ts).
const GROWABLE_SECTIONS = new Set<SectionId>(['cameras', 'recordings']);

// react-resizable-panels clips panels so content can never resize them. The other
// sections opt back into visible overflow so their dropdowns can escape the section
// (7f55868e); `minHeight: 0` stops flexbox from then sizing the panel by its content,
// which is what let expanded sections squeeze the camera list to nothing.
const NON_GROWABLE_PANEL_STYLE: React.CSSProperties = {overflow: 'visible', minHeight: 0};
// A section scrolls only while its panel is shorter than its content.
const SCROLLING_SECTION_STYLE: React.CSSProperties = {overflowY: 'auto', overflowX: 'hidden'};

type HeightById = Partial<Record<SectionId, number>>;

interface SectionMeasurements {
    /** Height shared by the section panels (px), excluding dividers; 0 until measured. */
    availablePx: number;
    /** Natural in-flow content height of each non-growable section (px). */
    contentPx: HeightById;
}

const sameHeights = (a: HeightById, b: HeightById, ids: readonly SectionId[]) =>
    ids.every(id => Math.abs((a[id] ?? -1) - (b[id] ?? -1)) < 0.5);

/**
 * Measures the height the section panels share and each non-growable section's
 * natural content height (`offsetHeight`, so open absolutely positioned dropdowns do
 * not count). Also reports which sections must scroll because their panel is shorter
 * than their content.
 */
function useSectionMeasurements(sections: readonly SectionId[]) {
    const groupElRef = useRef<HTMLDivElement | null>(null);
    const contentEls = useRef<Map<SectionId, HTMLElement>>(new Map());
    const boxEls = useRef<Map<SectionId, HTMLElement>>(new Map());
    const observerRef = useRef<ResizeObserver | null>(null);
    const refCbCache = useRef<Map<string, (el: HTMLElement | null) => void>>(new Map());
    const [measurements, setMeasurements] = useState<SectionMeasurements>({availablePx: 0, contentPx: {}});
    const [overflowing, setOverflowing] = useState<ReadonlySet<SectionId>>(() => new Set());

    const recompute = useCallback(() => {
        const groupEl = groupElRef.current;
        if (!groupEl) return;
        let availablePx = 0;
        groupEl.querySelectorAll<HTMLElement>(':scope > [data-panel-group] > [data-panel]')
            .forEach(panel => { availablePx += panel.getBoundingClientRect().height; });
        // The sidebar measures 0 while collapsed to its toolbar: keep the last layout.
        if (availablePx <= 0) return;
        const contentPx: HeightById = {};
        const nextOverflowing = new Set<SectionId>();
        for (const id of sections) {
            const content = contentEls.current.get(id);
            if (!content) continue;
            contentPx[id] = content.offsetHeight;
            const box = boxEls.current.get(id);
            if (box && content.offsetHeight > box.clientHeight + 1) nextOverflowing.add(id);
        }
        setMeasurements(prev =>
            Math.abs(prev.availablePx - availablePx) < 0.5 && sameHeights(prev.contentPx, contentPx, sections)
                ? prev
                : {availablePx, contentPx});
        setOverflowing(prev =>
            prev.size === nextOverflowing.size && [...nextOverflowing].every(id => prev.has(id))
                ? prev
                : nextOverflowing);
    }, [sections]);

    // Single observer watching the group, every section box and every content element.
    // useLayoutEffect runs after refs are attached but before paint, so the first
    // frame already has the measured layout (no squash flash).
    useLayoutEffect(() => {
        const observer = new ResizeObserver(() => recompute());
        observerRef.current = observer;
        if (groupElRef.current) observer.observe(groupElRef.current);
        contentEls.current.forEach((el) => observer.observe(el));
        boxEls.current.forEach((el) => observer.observe(el));
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

    const register = useCallback((kind: 'box' | 'content', id: SectionId) => {
        const key = `${kind}:${id}`;
        let cb = refCbCache.current.get(key);
        if (!cb) {
            const els = kind === 'box' ? boxEls : contentEls;
            cb = (el: HTMLElement | null) => {
                const prev = els.current.get(id);
                if (prev) observerRef.current?.unobserve(prev);
                if (el) {
                    els.current.set(id, el);
                    observerRef.current?.observe(el);
                } else {
                    els.current.delete(id);
                }
            };
            refCbCache.current.set(key, cb);
        }
        return cb;
    }, []);

    return {setGroupEl, register, measurements, overflowing};
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

    const { setGroupEl, register, measurements, overflowing } = useSectionMeasurements(visibleSections);
    // Cameras (or the recording browser) keep a guaranteed floor and get all spare
    // height; other sections get their content height when it fits and scroll when
    // it does not, so expanding a section can never hide the camera list.
    const plan = useMemo(() => planSidebarSections({
        sections: visibleSections,
        growable: GROWABLE_SECTIONS,
        contentPx: measurements.contentPx,
        availablePx: measurements.availablePx,
    }), [visibleSections, measurements]);

    const panelGroupRef = useRef<ImperativePanelGroupHandle>(null);
    const userResizedRef = useRef(false);
    const layoutKey = visibleSections.join('|');

    // A new set of sections (route change) gets a fresh maximized default — the
    // user hasn't expressed a preference for it yet.
    useLayoutEffect(() => {
        userResizedRef.current = false;
    }, [layoutKey]);

    // Keep the planned layout (cameras maximized above their floor) until the user
    // drags a divider. This must be imperative: the panel library applies defaultSize
    // once at mount. Re-asserting on every measurement change also survives the
    // startup window resize (launch → maximize). After a manual drag the user's sizes
    // stay; the minimum sizes still protect the camera floor and sections scroll.
    useLayoutEffect(() => {
        if (userResizedRef.current || measurements.availablePx <= 0) return;
        const allMeasured = visibleSections.every(
            id => GROWABLE_SECTIONS.has(id) || measurements.contentPx[id] != null,
        );
        if (!allMeasured) return;
        panelGroupRef.current?.setLayout(plan.sizes);
    }, [visibleSections, measurements, plan]);

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
                    The camera list keeps a guaranteed floor; other sections are sized
                    to their content when it fits and scroll internally when it does not. */}
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
                                        defaultSize={plan.sizes[index]}
                                        minSize={plan.minSizes[index]}
                                        style={growable ? undefined : NON_GROWABLE_PANEL_STYLE}
                                    >
                                        {growable ? (
                                            <div className="h-full min-h-0 flex flex-col overflow-hidden">
                                                <Component />
                                            </div>
                                        ) : (
                                            <div
                                                ref={register('box', id)}
                                                className="mocap-inner-section h-full min-h-0 bg-middark br-2"
                                                style={overflowing.has(id) ? SCROLLING_SECTION_STYLE : undefined}
                                            >
                                                <div ref={register('content', id)} className="flex flex-col ">
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
