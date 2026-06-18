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

const HANDLE_CLASS: Record<ResizeHandle, string> = {
    n:  'resize-handle resize-handle-n',
    s:  'resize-handle resize-handle-s',
    e:  'resize-handle resize-handle-e',
    w:  'resize-handle resize-handle-w',
    ne: 'resize-handle resize-handle-ne',
    nw: 'resize-handle resize-handle-nw',
    se: 'resize-handle resize-handle-se',
    sw: 'resize-handle resize-handle-sw',
};

const HANDLES: ResizeHandle[] = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'];

export default function PipelineProgressSnackbar() {
    const dispatch = useAppDispatch();
    const groups = useAppSelector(selectGroupedPipelinesAll);
    const activeCount = useAppSelector(selectActiveBasePipelineCount);
    const open = useAppSelector(selectSnackbarVisible);
    const dismissedIds = useAppSelector(selectDismissedBasePipelineIds);
    const [collapsed, setCollapsed] = React.useState(false);

    const [dragPos, setDragPos] = React.useState<{left: number; bottom: number} | null>(null);
    const [size, setSize] = React.useState({width: DEFAULT_WIDTH, height: DEFAULT_HEIGHT});

    const containerRef = React.useRef<HTMLDivElement>(null);
    const dragRef = React.useRef<{
        startMx: number; startMy: number; startLeft: number; startBottom: number;
    } | null>(null);
    const resizeRef = React.useRef<{
        handle: ResizeHandle;
        startMx: number; startMy: number;
        startW: number; startH: number;
        startLeft: number; startBottom: number;
    } | null>(null);

    const handleHeaderMouseDown = React.useCallback((e: React.MouseEvent) => {
        if (e.button !== 0) return;
        const rect = containerRef.current?.getBoundingClientRect();
        if (!rect) return;
        dragRef.current = {
            startMx: e.clientX, startMy: e.clientY,
            startLeft: rect.left,
            startBottom: window.innerHeight - rect.top - rect.height,
        };
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
            startLeft: rect.left,
            startBottom: window.innerHeight - rect.top - rect.height,
        };
    }, []);

    React.useEffect(() => {
        const onMove = (e: MouseEvent) => {
            if (dragRef.current) {
                const dx = e.clientX - dragRef.current.startMx;
                const dy = e.clientY - dragRef.current.startMy;
                setDragPos({
                    left: Math.max(0, dragRef.current.startLeft + dx),
                    bottom: Math.max(0, dragRef.current.startBottom - dy),
                });
            }
            if (resizeRef.current) {
                const {handle, startMx, startMy, startW, startH, startLeft, startBottom} = resizeRef.current;
                const dx = e.clientX - startMx;
                const dy = e.clientY - startMy;

                let newW = startW, newH = startH;
                let newLeft = startLeft, newBottom = startBottom;
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
                    newBottom = startBottom + startH - newH;
                    posChanged = true;
                }

                setSize({width: newW, height: newH});
                if (posChanged) setDragPos({left: newLeft, bottom: newBottom});
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
        ? {left: dragPos.left, bottom: dragPos.bottom, width: size.width}
        : {width: size.width};

    return (
        <div
            ref={containerRef}
            className={`snackbar-main-container-modal border-1 bg-dark br-3 p-1 ${dragPos ? 'snackbar-container-dragged' : 'snackbar-container'}`}
            style={containerStyle}
        >
            {HANDLES.filter(h => !collapsed || h === 'e' || h === 'w').map(h => (
                <div key={h} className={HANDLE_CLASS[h]} onMouseDown={(e) => startResize(h, e)}/>
            ))}

            <div className={
                `pipeline-progress-toast-flyout bg-middark flex flex-col w-full overflow-hidden` +
                ` pipeline-toast-flyout shadow-lg` +
                (hasRunningVisible ? ' pipeline-toast-flyout--running' : '')
            } style={{
                height: collapsed ? 'auto' : '100%',
            }}>
                <div
                    onMouseDown={handleHeaderMouseDown}
                    className="flex flex-row items-center flex-shrink-0 px-2 pt-1 pb-1 gap-2 cursor-grab select-none"
                    style={{
                        borderBottom: collapsed ? 'none' : '1px solid var(--color-border-secondary)',
                    }}
                >
                    {collapsed ? (
                        <div className="flex-1 min-w-0 mr-1">
                            <div className="flex flex-row items-center justify-content-space-between" style={{marginBottom: 2}}>
                                <p className="text flex-1 mr-1 m-0 truncate">
                                    {summaryLabel}
                                </p>
                                <p className="text  text-gray flex-shrink-0 m-0">
                                    {summaryProgress}%
                                </p>
                            </div>
                            {summaryGroup?.isActive && (
                                <div className="update-progress-track progress-track-sm">
                                    <div className="update-progress-fill h-full progress-fill-sm" style={{width: `${summaryProgress}%`}}/>
                                </div>
                            )}
                        </div>
                    ) : (
                        <p className="text md text-white flex-1 m-0 ">Pipeline Progress</p>
                    )}

                    {hasRunningVisible && (
                        <div className="flex-shrink-0 mr-1 w-7 h-7 rounded-full bg-info" style={{
                            animation: 'fmcPulse 1.4s ease-in-out infinite',
                        }}/>
                    )}

                    <IconButton
                        icon="clear-icon"
                        className="icon-size-25 p-01 mr-2"
                        onMouseDown={e => e.stopPropagation()}
                        onClick={() => dispatch(allPipelinesCleared())}
                        disabled={visibleGroups.length === 0}
                        tooltip={true}
                        tooltipText="Clear all pipelines"
                        tooltipPosition="pos-bottom"
                    />
                    <IconButton
                        icon={collapsed ? 'arrowup-icon' : 'arrowdown-icon'}
                        className="icon-size-25 p-01"
                        onMouseDown={e => e.stopPropagation()}
                        onClick={() => setCollapsed(c => !c)}
                        tooltip={true}
                        tooltipText={collapsed ? "Expand" : "Collapse"}
                        tooltipPosition="pos-bottom"
                    />

                    {hasRunningVisible && (
                        <IconButton
                            icon="close-icon"
                            className="icon-size-25 p-01 text-error"
                            onMouseDown={e => e.stopPropagation()}
                            onClick={() => dispatch(stopAllPipelines())}
                            tooltip={true}
                            tooltipText="Stop all pipelines"
                            tooltipPosition="pos-bottom"
                        />
                    )}


                    <IconButton
                        icon="close-icon"
                        className="icon-size-25 p-01"
                        onMouseDown={e => e.stopPropagation()}
                        onClick={() => dispatch(pipelineSnackbarHidden())}
                        tooltip={true}
                        tooltipText="Close"
                        tooltipPosition="pos-bottom"
                    />

                </div>

                {!collapsed && (
                    <div className="overflow-y flex-1 min-h-0 inner-content">
                        {visibleGroups.length === 0 ? (
                            <div className="flex justify-center py-4">
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