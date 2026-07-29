import React, {memo, useMemo, useState} from 'react';
import {Box, Tooltip, Typography} from '@mui/material';
import {alpha, useTheme} from '@mui/material/styles';
import {useTranslation} from 'react-i18next';
import {
    barWidthPercentInViewport,
    buildRulerTicks,
    formatBarDuration,
    formatRulerTick,
    shouldShowBarDurationLabel,
    type PipelineTimelineViewModel,
    type TimelineRowView,
    type VisibleTimelineWindow,
} from '@/components/pipeline-metrics/pipelineTimelineModel';
import {getPipelineStageRowTooltip} from '@/components/pipeline-metrics/pipelineStageTooltips';
import {CATEGORY_COLORS} from '@/components/pipeline-metrics/pipelineTaskTopology';
import IconButton from '@/components/ui-components/IconButton';
import {useTimelineChartZoom} from '@/hooks/useTimelineChartZoom';

const ROW_HEIGHT = 22;
const LABEL_WIDTH = 280;
const RULER_HEIGHT = 28;
const CHART_PADDING_RIGHT = 8;

function TimelineRowTooltipTitle({
    description,
    durationLabel,
}: {
    description: string;
    durationLabel: string;
}): React.ReactElement {
    return (
        <Box>
            <Typography variant="body2">{description}</Typography>
            <Typography variant="caption" color="text.secondary" sx={{display: 'block', mt: 0.5}}>
                {durationLabel}
            </Typography>
        </Box>
    );
}

type Props = {
    model: PipelineTimelineViewModel;
    selectedTaskId: string | null;
    onSelectTask: (taskId: string | null) => void;
};

function TimelineLinks({
    model,
    scrollTop,
}: {
    model: PipelineTimelineViewModel;
    scrollTop: number;
}): React.ReactElement {
    const height = model.rows.length * ROW_HEIGHT;
    const paths = model.edges.map(edge => {
        const fromY = edge.fromRowIndex * ROW_HEIGHT + ROW_HEIGHT / 2 - scrollTop;
        const toY = edge.toRowIndex * ROW_HEIGHT + ROW_HEIGHT / 2 - scrollTop;
        if (fromY < -ROW_HEIGHT || toY > height + ROW_HEIGHT) return null;
        const x1 = LABEL_WIDTH + 8;
        const x2 = LABEL_WIDTH + 24;
        const midX = (x1 + x2) / 2;
        return `M ${x1} ${fromY} C ${midX} ${fromY}, ${midX} ${toY}, ${x2} ${toY}`;
    }).filter(Boolean);

    return (
        <svg
            style={{
                position: 'absolute',
                left: 0,
                top: RULER_HEIGHT,
                width: '100%',
                height,
                pointerEvents: 'none',
                overflow: 'visible',
            }}
        >
            {paths.map((d, i) => (
                <path
                    key={i}
                    d={d!}
                    fill="none"
                    stroke="currentColor"
                    strokeOpacity={0.25}
                    strokeWidth={1}
                />
            ))}
        </svg>
    );
}

const TimelineRow = memo(function TimelineRow({
    row,
    visibleWindow,
    selected,
    onSelect,
}: {
    row: TimelineRowView;
    visibleWindow: VisibleTimelineWindow;
    selected: boolean;
    onSelect: () => void;
}) {
    const theme = useTheme();
    const {t} = useTranslation();
    const {leftPct, widthPct, visible} = barWidthPercentInViewport(
        row,
        visibleWindow.visibleStartMs,
        visibleWindow.visibleDurationMs,
    );
    const parentSpan =
        row.parentSpanStartMs != null && row.parentSpanEndMs != null
            ? barWidthPercentInViewport(
                {barStartMs: row.parentSpanStartMs, barEndMs: row.parentSpanEndMs},
                visibleWindow.visibleStartMs,
                visibleWindow.visibleDurationMs,
            )
            : null;
    const color = CATEGORY_COLORS[row.category];
    const durationLabel = formatBarDuration(row.durationMs);
    const showDurationOnBar = visible && shouldShowBarDurationLabel(widthPct, durationLabel);
    const rowTip = getPipelineStageRowTooltip(row.sourceKey, t);
    const tooltipTitle = (
        <TimelineRowTooltipTitle description={rowTip.long} durationLabel={durationLabel} />
    );

    return (
        <Box
            onClick={onSelect}
            sx={{
                display: 'flex',
                alignItems: 'center',
                height: ROW_HEIGHT,
                cursor: 'pointer',
                minWidth: 0,
                opacity: row.stale ? 0.4 : 1,
                bgcolor: selected ? alpha(theme.palette.primary.main, 0.08) : 'transparent',
                '&:hover': {bgcolor: alpha(theme.palette.action.hover, 0.04)},
            }}
        >
            <Box
                sx={{
                    width: LABEL_WIDTH,
                    minWidth: LABEL_WIDTH,
                    maxWidth: LABEL_WIDTH,
                    flexShrink: 0,
                    overflow: 'hidden',
                    px: 1,
                    '& > span': {
                        display: 'block',
                        width: '100%',
                        minWidth: 0,
                        overflow: 'hidden',
                    },
                }}
            >
                <Tooltip title={tooltipTitle} placement="top" enterDelay={200}>
                    <Box
                        component="span"
                        sx={{
                            display: 'block',
                            width: '100%',
                            minWidth: 0,
                            overflow: 'hidden',
                        }}
                    >
                        <Typography
                            noWrap
                            variant="caption"
                            sx={{
                                display: 'block',
                                width: '100%',
                                fontSize: '0.7rem',
                                color: 'text.secondary',
                                cursor: 'help',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                            }}
                        >
                            {row.label}
                        </Typography>
                    </Box>
                </Tooltip>
            </Box>
            <Box sx={{flex: 1, position: 'relative', height: '100%', pr: 1, minWidth: 0, overflow: 'hidden'}}>
                {parentSpan?.visible && (
                    <Box
                        sx={{
                            position: 'absolute',
                            top: 2,
                            bottom: 2,
                            left: `${parentSpan.leftPct}%`,
                            width: `${parentSpan.widthPct}%`,
                            borderLeft: 1,
                            borderRight: 1,
                            borderColor: alpha(color, 0.35),
                            bgcolor: alpha(color, 0.08),
                            pointerEvents: 'none',
                        }}
                    />
                )}
                {visible && (
                    <Tooltip title={tooltipTitle} placement="top" enterDelay={200}>
                        <Box
                            sx={{
                                position: 'absolute',
                                top: 4,
                                bottom: 4,
                                left: `${leftPct}%`,
                                width: `${widthPct}%`,
                                minWidth: 2,
                                borderRadius: 0.5,
                                bgcolor: color,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                overflow: 'hidden',
                            }}
                        >
                            {showDurationOnBar && (
                                <Typography
                                    noWrap
                                    variant="caption"
                                    sx={{
                                        fontSize: '0.6rem',
                                        fontWeight: 600,
                                        lineHeight: 1,
                                        color: theme.palette.common.white,
                                        textShadow: '0 0 2px rgba(0,0,0,0.75)',
                                        pointerEvents: 'none',
                                        px: 0.25,
                                    }}
                                >
                                    {durationLabel}
                                </Typography>
                            )}
                        </Box>
                    </Tooltip>
                )}
            </Box>
        </Box>
    );
});

function SelectedRowDetails({row}: {row: TimelineRowView}): React.ReactElement {
    const {t} = useTranslation();
    const rowTip = getPipelineStageRowTooltip(row.sourceKey, t);
    return (
        <Typography variant="caption" color="text.secondary" component="div">
            <Box component="span" sx={{fontWeight: 600}}>{row.label}</Box>
            {' · '}
            {row.durationMs.toFixed(2)} ms
            {row.stale ? ' · stale' : ''}
            <Typography variant="caption" color="text.secondary" display="block" sx={{mt: 0.25}}>
                {rowTip.long}
            </Typography>
        </Typography>
    );
}

export function PipelineNetworkTimeline({model, selectedTaskId, onSelectTask}: Props): React.ReactElement {
    const theme = useTheme();
    const {t} = useTranslation();
    const [scrollTop, setScrollTop] = useState(0);
    const {
        containerRef,
        visibleWindow,
        isZoomed,
        resetZoom,
        zoomIn,
        zoomOut,
        chartCursor,
        chartHandlers,
    } = useTimelineChartZoom({
        baseStartMs: model.windowStartMs,
        baseDurationMs: model.windowDurationMs,
        labelWidthPx: LABEL_WIDTH,
        chartPaddingRightPx: CHART_PADDING_RIGHT,
    });

    const rulerTicks = useMemo(
        () => buildRulerTicks(visibleWindow.visibleDurationMs),
        [visibleWindow.visibleDurationMs],
    );

    const selectedRow = model.rows.find(r => r.taskId === selectedTaskId)
        ?? model.orphanUiRows.find(r => r.taskId === selectedTaskId)
        ?? null;

    return (
        <Box sx={{display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0}}>
            <Box
                sx={{
                    display: 'flex',
                    height: RULER_HEIGHT,
                    borderBottom: 1,
                    borderColor: 'divider',
                    flexShrink: 0,
                }}
            >
                <Box
                    sx={{
                        width: LABEL_WIDTH,
                        flexShrink: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'flex-end',
                        gap: 0.25,
                        pr: 0.5,
                    }}
                >
                    <IconButton icon="minus-icon" title={t('zoomOut')} onClick={zoomOut} />
                    <IconButton icon="plus-icon" title={t('zoomIn')} onClick={zoomIn} />
                    {isZoomed && (
                        <IconButton icon="back-icon" title={t('resetZoom')} onClick={resetZoom} />
                    )}
                </Box>
                <Box sx={{flex: 1, position: 'relative', pr: 1}}>
                    {rulerTicks.map(tick => (
                        <Typography
                            key={tick}
                            variant="caption"
                            sx={{
                                position: 'absolute',
                                left: `${(tick / visibleWindow.visibleDurationMs) * 100}%`,
                                transform: 'translateX(-50%)',
                                fontSize: '0.65rem',
                                color: 'text.disabled',
                                top: 4,
                            }}
                        >
                            {formatRulerTick(tick + (visibleWindow.visibleStartMs - model.windowStartMs))}
                        </Typography>
                    ))}
                </Box>
            </Box>

            <Box
                ref={containerRef}
                onScroll={event => setScrollTop(event.currentTarget.scrollTop)}
                sx={{
                    flex: 1,
                    overflow: 'auto',
                    position: 'relative',
                    cursor: chartCursor,
                }}
                {...chartHandlers}
            >
                <TimelineLinks model={model} scrollTop={scrollTop} />
                {model.rows.length === 0 ? (
                    <Typography variant="body2" color="text.secondary" sx={{p: 2}}>
                        No pipeline task events in the current {model.frameStart != null ? `${model.frameEnd! - model.frameStart! + 1}-frame` : ''} window.
                        {model.paused ? ' (paused)' : ''}
                    </Typography>
                ) : (
                    model.rows.map(row => (
                        <TimelineRow
                            key={row.taskId}
                            row={row}
                            visibleWindow={visibleWindow}
                            selected={row.taskId === selectedTaskId}
                            onSelect={() => onSelectTask(row.taskId === selectedTaskId ? null : row.taskId)}
                        />
                    ))
                )}
                {model.orphanUiRows.length > 0 && (
                    <Box sx={{mt: 1, borderTop: 1, borderColor: alpha(theme.palette.divider, 0.5)}}>
                        <Typography variant="caption" color="text.secondary" sx={{px: 1, py: 0.5, display: 'block'}}>
                            Events without frame context
                        </Typography>
                        {model.orphanUiRows.map(row => (
                            <TimelineRow
                                key={row.taskId}
                                row={row}
                                visibleWindow={visibleWindow}
                                selected={row.taskId === selectedTaskId}
                                onSelect={() => onSelectTask(row.taskId === selectedTaskId ? null : row.taskId)}
                            />
                        ))}
                    </Box>
                )}
            </Box>

            {selectedRow && (
                <Box sx={{p: 1, borderTop: 1, borderColor: 'divider', flexShrink: 0}}>
                    <SelectedRowDetails row={selectedRow} />
                </Box>
            )}
        </Box>
    );
}
