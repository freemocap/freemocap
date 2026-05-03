import * as React from 'react';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import CloseIcon from '@mui/icons-material/Close';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import StopCircleIcon from '@mui/icons-material/StopCircle';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {
    allPipelinesCleared,
    pipelineDismissed,
    pipelineSnackbarHidden,
    pipelineSnackbarShown,
    selectActiveBasePipelineCount,
    selectDismissedBasePipelineIds,
    selectGroupedPipelinesAll,
    selectSnackbarVisible,
} from '@/store/slices/pipelines';
import {stopAllPipelines} from '@/store/slices/pipelines/pipelines-thunks';
import PipelineGroupCard from './PipelineGroupCard';
import {useTheme} from "@mui/material";

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

function handleSx(h: ResizeHandle) {
    const base = {position: 'absolute', zIndex: 10} as const;
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
    const theme = useTheme()
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

    // Summary info for collapsed view — prefer active, fall back to most recent
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

    const positionSx = dragPos
        ? {position: 'fixed', left: dragPos.left, top: dragPos.top, zIndex: 1400}
        : {position: 'fixed', bottom: 8, right: 8, zIndex: 1400};

    return (
        <Box
            ref={containerRef}
            sx={{
                ...positionSx,
                width: size.width,
                // collapsed: auto-height (just the header); expanded: full tracked height
                ...(collapsed ? {} : {height: size.height}),
            }}
        >
            {/* Width handles always available; height/corner handles only when expanded */}
            {HANDLES.filter(h => !collapsed || h === 'e' || h === 'w').map(h => (
                <Box key={h} sx={handleSx(h)} onMouseDown={(e) => startResize(h, e)}/>
            ))}

            <Paper
                elevation={6}
                sx={{
                    width: '100%',
                    height: collapsed ? 'auto' : '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    borderRadius: 2,
                    overflow: 'hidden',
                    border: 1,
                    borderColor: hasRunningVisible ? '#FF00FF' : 'transparent',
                }}
            >
                {/* Header — always visible */}
                <Box
                    onMouseDown={handleHeaderMouseDown}
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        px: 1,
                        py: 0.75,
                        borderBottom: collapsed ? 0 : 1,
                        borderColor: 'divider',
                        flexShrink: 0,
                        cursor: 'grab',
                        userSelect: 'none',
                        '&:active': {cursor: 'grabbing'},
                    }}
                >
                    {collapsed ? (
                        // Collapsed summary: name + progress bar + %
                        <Box sx={{flex: 1, minWidth: 0, mr: 1}}>
                            <Box sx={{display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', mb: 0.25}}>
                                <Typography variant="caption" noWrap sx={{fontSize: '0.72rem', flex: 1, mr: 0.5}}>
                                    {summaryLabel}
                                </Typography>
                                <Typography variant="caption" color="text.secondary" sx={{fontSize: '0.68rem', flexShrink: 0}}>
                                    {summaryProgress}%
                                </Typography>
                            </Box>
                            {summaryGroup?.isActive && (
                                <LinearProgress
                                    variant="determinate"
                                    value={summaryProgress}
                                    sx={{height: 3, borderRadius: 1}}
                                />
                            )}
                        </Box>
                    ) : (
                        // Expanded title
                        <Typography variant="subtitle2" sx={{flex: 1}}>
                            Pipeline Progress
                        </Typography>
                    )}

                    {hasRunningVisible && (
                        <Box sx={{
                            width: 7, height: 7, borderRadius: '50%', bgcolor: 'primary.main', mr: 1, flexShrink: 0,
                            animation: 'fmcPulse 1.4s ease-in-out infinite',
                            '@keyframes fmcPulse': {
                                '0%, 100%': {opacity: 1, transform: 'scale(1)'},
                                '50%': {opacity: 0.3, transform: 'scale(0.7)'},
                            },
                        }}/>
                    )}

                    <IconButton
                        size="small"
                        onMouseDown={e => e.stopPropagation()}
                        onClick={() => setCollapsed(c => !c)}
                        sx={{p: 0.25}}
                    >
                        {collapsed ? <ExpandLessIcon fontSize="small"/> : <ExpandMoreIcon fontSize="small"/>}
                    </IconButton>

                    {hasRunningVisible && (
                        <IconButton
                            size="small"
                            onMouseDown={e => e.stopPropagation()}
                            onClick={() => dispatch(stopAllPipelines())}
                            title="Stop all pipelines"
                            sx={{p: 0.25, color: 'error.main'}}
                        >
                            <StopCircleIcon fontSize="small"/>
                        </IconButton>
                    )}

                    <IconButton
                        size="small"
                        onMouseDown={e => e.stopPropagation()}
                        onClick={() => dispatch(allPipelinesCleared())}
                        disabled={visibleGroups.length === 0}
                        title="Clear all pipelines"
                        sx={{p: 0.25}}
                    >
                        <DeleteSweepIcon fontSize="small"/>
                    </IconButton>

                    <IconButton
                        size="small"
                        onMouseDown={e => e.stopPropagation()}
                        onClick={() => dispatch(pipelineSnackbarHidden())}
                        sx={{p: 0.25}}
                    >
                        <CloseIcon fontSize="small"/>
                    </IconButton>

                    <DragIndicatorIcon sx={{fontSize: '0.9rem', color: 'text.disabled', ml: 0.25, flexShrink: 0, cursor: 'grab'}}/>
                </Box>

                {/* Scrollable content — hidden when collapsed */}
                {!collapsed && (
                    <Box sx={{overflow: 'auto', flex: 1, minHeight: 0}}>
                        {visibleGroups.length === 0 ? (
                            <Box sx={{py: 2, display: 'flex', justifyContent: 'center'}}>
                                <Typography variant="caption" color="text.secondary">
                                    No active pipelines
                                </Typography>
                            </Box>
                        ) : (
                            visibleGroups.map((group) => (
                                <PipelineGroupCard
                                    key={group.basePipelineId}
                                    group={group}
                                    onDismiss={() => dispatch(pipelineDismissed(group.basePipelineId))}
                                />
                            ))
                        )}
                    </Box>
                )}
            </Paper>
        </Box>
    );
}
