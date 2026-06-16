import * as React from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {
    allPipelinesCleared,
    pipelineDismissed,
    pipelineSnackbarHidden,
    selectActiveBasePipelineCount,
    selectDismissedBasePipelineIds,
    selectGroupedPipelinesAll,
    selectSnackbarVisible,
} from '@/store/slices/pipelines';
import {stopAllPipelines} from '@/store/slices/pipelines/pipelines-thunks';
import PipelineGroupCard from './PipelineGroupCard';
import IconButton from '@/components/ui-components/IconButton';

const DEFAULT_WIDTH = 360;
const DEFAULT_HEIGHT = 420;
const MIN_WIDTH = 240;
const MIN_HEIGHT = 100;

type ResizeHandle = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw';

const CURSOR: Record<ResizeHandle, string> = {
    n: 'ns-resize',    s: 'ns-resize',
    e: 'ew-resize',    w: 'ew-resize',
    ne: 'nesw-resize', sw: 'nesw-resize',
    nw: 'nwse-resize', se: 'nwse-resize',
};

const EDGE = 6;
const CORN = 14;

function handleStyle(h: ResizeHandle): React.CSSProperties {
    const base: React.CSSProperties = {position: 'absolute', zIndex: 10};
    switch (h) {
        case 'n':  return {...base, top: -EDGE/2, left: CORN, right: CORN, height: EDGE, cursor: CURSOR.n};
        case 's':  return {...base, bottom: -EDGE/2, left: CORN, right: CORN, height: EDGE, cursor: CURSOR.s};
        case 'e':  return {...base, right: -EDGE/2, top: CORN, bottom: CORN, width: EDGE, cursor: CURSOR.e};
        case 'w':  return {...base, left: -EDGE/2, top: CORN, bottom: CORN, width: EDGE, cursor: CURSOR.w};
        case 'nw': return {...base, top: -EDGE/2, left: -EDGE/2, width: CORN, height: CORN, cursor: CURSOR.nw};
        case 'ne': return {...base, top: -EDGE/2, right: -EDGE/2, width: CORN, height: CORN, cursor: CURSOR.ne};
        case 'sw': return {...base, bottom: -EDGE/2, left: -EDGE/2, width: CORN, height: CORN, cursor: CURSOR.sw};
        case 'se': return {...base, bottom: -EDGE/2, right: -EDGE/2, width: CORN, height: CORN, cursor: CURSOR.se};
    }
}

const HANDLES: ResizeHandle[] = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'];

export default function PipelineProgressSnackbar() {
    const dispatch = useAppDispatch();
    const groups = useAppSelector(selectGroupedPipelinesAll);
    const activeCount = useAppSelector(selectActiveBasePipelineCount);
    const open = useAppSelector(selectSnackbarVisible);
    const dismissedIds = useAppSelector(selectDismissedBasePipelineIds);
    const [collapsed, setCollapsed] = React.useState(false);

    const [dragPos, setDragPos] = React.useState<{left: number; top: number} | null>(null);
    const [size, setSize] = React.useState({width: DEFAULT_WIDTH, height: DEFAULT_HEIGHT});

    const containerRef = React.useRef<HTMLDivElement>(null);
    const dragRef = React.useRef<{
        startMx: number; startMy: number; startLeft: number; startTop: number;
    } | null>(null);
    const resizeRef = React.useRef<{
        handle: ResizeHandle;
        startMx: number; startMy: number;
        startW: number; startH: number;
        startLeft: number; startTop: number;
    } | null>(null);

    const handleHeaderMouseDown = React.useCallback((e: React.MouseEvent) => {
        if (e.button !== 0) return;
        const rect = containerRef.current?.getBoundingClientRect();
        if (!rect) return;
        dragRef.current = {startMx: e.clientX, startMy: e.clientY, startLeft: rect.left, startTop: rect.top};
        e.preventDefault();
    }, []);

    const startResize = React.useCallback((handle: ResizeHandle, e: React.MouseEvent) => {
        if (e.button !== 0) return;
        e.preventDefault();
        e.stopPropagation();
        const rect = containerRef.current?.getBoundingClientRect();
        if (!rect) return;
        resizeRef.current = {
            handle,
            startMx: e.clientX, startMy: e.clientY,
            startW: rect.width, startH: rect.height,
            startLeft: rect.left, startTop: rect.top,
        };
    }, []);

    React.useEffect(() => {
        const onMove = (e: MouseEvent) => {
            if (dragRef.current) {
                const dx = e.clientX - dragRef.current.startMx;
                const dy = e.clientY - dragRef.current.startMy;
                setDragPos({
                    left: Math.max(0, dragRef.current.startLeft + dx),
                    top: Math.max(0, dragRef.current.startTop + dy),
                });
            }
            if (resizeRef.current) {
                const {handle, startMx, startMy, startW, startH, startLeft, startTop} = resizeRef.current;
                const dx = e.clientX - startMx;
                const dy = e.clientY - startMy;

                let newW = startW, newH = startH;
                let newLeft = startLeft, newTop = startTop;
                let posChanged = false;

                if (handle.includes('e')) newW = Math.max(MIN_WIDTH, startW + dx);
                if (handle.includes('s')) newH = Math.max(MIN_HEIGHT, startH + dy);
                if (handle.includes('w')) {
                    newW = Math.max(MIN_WIDTH, startW - dx);
                    newLeft = startLeft + startW - newW;
                    posChanged = true;
                }
                if (handle.includes('n')) {
                    newH = Math.max(MIN_HEIGHT, startH - dy);
                    newTop = startTop + startH - newH;
                    posChanged = true;
                }

                setSize({width: newW, height: newH});
                if (posChanged) setDragPos({left: newLeft, top: newTop});
            }
        };
        const onUp = () => { dragRef.current = null; resizeRef.current = null; };
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
        return () => {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
        };
    }, []);

    const visibleGroups = groups.filter(g => !dismissedIds.includes(g.basePipelineId));
    const hasRunningVisible = visibleGroups.some(g => !g.isComplete && !g.isFailed);

    const summaryGroup = visibleGroups.find(g => g.isActive) ?? visibleGroups[0] ?? null;
    const summaryProgress = summaryGroup
        ? (summaryGroup.aggregator?.progress
            ?? (summaryGroup.videoNodes.length > 0
                ? Math.round(summaryGroup.videoNodes.reduce((s, n) => s + n.progress, 0) / summaryGroup.videoNodes.length)
                : 0))
        : 0;
    const summaryLabel = summaryGroup
        ? `${summaryGroup.recordingName || summaryGroup.basePipelineId}${visibleGroups.length > 1 ? ` +${visibleGroups.length - 1}` : ''}`
        : 'No active pipelines';

    if (!open) return null;

    const containerStyle: React.CSSProperties = dragPos
        ? {position: 'fixed', left: dragPos.left, top: dragPos.top, zIndex: 1400, width: size.width, ...(collapsed ? {} : {height: size.height})}
        : {position: 'fixed', bottom: 8, right: 8, zIndex: 1400, width: size.width, ...(collapsed ? {} : {height: size.height})};

    return (
        <div ref={containerRef} style={containerStyle}>
            {HANDLES.filter(h => !collapsed || h === 'e' || h === 'w').map(h => (
                <div key={h} style={handleStyle(h)} onMouseDown={(e) => startResize(h, e)}/>
            ))}

            <div className="bg-middark flex flex-col w-full overflow-hidden" style={{
                height: collapsed ? 'auto' : '100%',
                borderRadius: 8,
                border: `1px solid ${hasRunningVisible ? '#FF00FF' : 'transparent'}`,
                boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
            }}>
                <div
                    onMouseDown={handleHeaderMouseDown}
                    className="flex flex-row items-center flex-shrink-0"
                    style={{
                        padding: '6px 8px',
                        borderBottom: collapsed ? 'none' : '1px solid var(--color-border-secondary)',
                        cursor: 'grab',
                        userSelect: 'none',
                    }}
                >
                    {collapsed ? (
                        <div className="flex-1 min-w-0 mr-1">
                            <div className="flex flex-row items-center justify-content-space-between" style={{marginBottom: 2}}>
                                <p className="text sm flex-1 mr-1 m-0" style={{overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.72rem'}}>
                                    {summaryLabel}
                                </p>
                                <p className="text sm text-gray flex-shrink-0 m-0" style={{fontSize: '0.68rem'}}>
                                    {summaryProgress}%
                                </p>
                            </div>
                            {summaryGroup?.isActive && (
                                <div className="update-progress-track" style={{height: 3, borderRadius: 2}}>
                                    <div className="update-progress-fill h-full" style={{width: `${summaryProgress}%`, borderRadius: 2}}/>
                                </div>
                            )}
                        </div>
                    ) : (
                        <p className="text md text-white flex-1 m-0" style={{fontWeight: 600}}>Pipeline Progress</p>
                    )}

                    {hasRunningVisible && (
                        <div className="flex-shrink-0 mr-1" style={{
                            width: 7, height: 7, borderRadius: '50%', backgroundColor: 'var(--color-info)',
                            animation: 'fmcPulse 1.4s ease-in-out infinite',
                        }}/>
                    )}

                    <IconButton
                        icon={collapsed ? 'expand-icon' : 'collapse-icon'}
                        className="icon-size-25 p-01"
                        onMouseDown={e => e.stopPropagation()}
                        onClick={() => setCollapsed(c => !c)}
                    />

                    {hasRunningVisible && (
                        <IconButton
                            icon="close-icon"
                            className="icon-size-25 p-01"
                            onMouseDown={e => e.stopPropagation()}
                            onClick={() => dispatch(stopAllPipelines())}
                            title="Stop all pipelines"
                            style={{color: 'var(--color-error)'}}
                        />
                    )}

                    <IconButton
                        icon="clear-icon"
                        className="icon-size-25 p-01"
                        onMouseDown={e => e.stopPropagation()}
                        onClick={() => dispatch(allPipelinesCleared())}
                        disabled={visibleGroups.length === 0}
                        title="Clear all pipelines"
                    />

                    <IconButton
                        icon="close-icon"
                        className="icon-size-25 p-01"
                        onMouseDown={e => e.stopPropagation()}
                        onClick={() => dispatch(pipelineSnackbarHidden())}
                    />

                    <span className="icon settings-icon icon-size-20 flex-shrink-0" style={{color: 'var(--color-text-disabled)', marginLeft: 2, cursor: 'grab'}}/>
                </div>

                {!collapsed && (
                    <div className="overflow-y flex-1 min-h-0">
                        {visibleGroups.length === 0 ? (
                            <div className="flex justify-center" style={{paddingTop: 16, paddingBottom: 16}}>
                                <p className="text sm text-gray">No active pipelines</p>
                            </div>
                        ) : (
                            visibleGroups.map((group) => (
                                <PipelineGroupCard
                                    key={group.basePipelineId}
                                    group={group}
                                    onDismiss={() => dispatch(pipelineDismissed(group.basePipelineId))}
                                />
                            ))
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
