import React, {memo, useMemo, useRef} from 'react';
import {Box, Tooltip, Typography} from '@mui/material';
import {alpha, useTheme} from '@mui/material/styles';
import {useTranslation} from 'react-i18next';
import {ProgressiveTooltip} from '@/components/framerate-viewer/FramerateStatisticsView';
import {
    barWidthPercent,
    formatBarDuration,
    formatRulerTick,
    shouldShowBarDurationLabel,
    type PipelineTimelineViewModel,
    type TimelineRowView,
} from '@/components/pipeline-metrics/pipelineTimelineModel';
import {getPipelineStageRowTooltip} from '@/components/pipeline-metrics/pipelineStageTooltips';
import {CATEGORY_COLORS} from '@/components/pipeline-metrics/pipelineTaskTopology';

const ROW_HEIGHT = 22;
const LABEL_WIDTH = 280;
const RULER_HEIGHT = 28;

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
    model,
    selected,
    onSelect,
}: {
    row: TimelineRowView;
    model: PipelineTimelineViewModel;
    selected: boolean;
    onSelect: () => void;
}) {
    const theme = useTheme();
    const {t} = useTranslation();
    const {leftPct, widthPct} = barWidthPercent(row, model.windowStartMs, model.windowDurationMs);
    const color = CATEGORY_COLORS[row.category];
    const durationLabel = formatBarDuration(row.durationMs);
    const showDurationOnBar = shouldShowBarDurationLabel(widthPct, durationLabel);
    const rowTip = getPipelineStageRowTooltip(row.sourceKey, t);

    return (
        <Box
            onClick={onSelect}
            sx={{
                display: 'flex',
                alignItems: 'center',
                height: ROW_HEIGHT,
                cursor: 'pointer',
                opacity: row.stale ? 0.4 : 1,
                bgcolor: selected ? alpha(theme.palette.primary.main, 0.08) : 'transparent',
                '&:hover': {bgcolor: alpha(theme.palette.action.hover, 0.04)},
            }}
        >
            <ProgressiveTooltip shortInfo={rowTip.short} longInfo={rowTip.long} alwaysShowLong>
                <Typography
                    noWrap
                    variant="caption"
                    sx={{
                        width: LABEL_WIDTH,
                        flexShrink: 0,
                        px: 1,
                        fontSize: '0.7rem',
                        color: 'text.secondary',
                        cursor: 'help',
                    }}
                >
                    {row.label}
                </Typography>
            </ProgressiveTooltip>
            <Box sx={{flex: 1, position: 'relative', height: '100%', pr: 1}}>
                <Tooltip
                    title={
                        <Box>
                            <Typography variant="body2">{rowTip.long}</Typography>
                            <Typography variant="caption" color="text.secondary" sx={{display: 'block', mt: 0.5}}>
                                {durationLabel}
                            </Typography>
                        </Box>
                    }
                    placement="top"
                    enterDelay={200}
                >
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
    const scrollRef = useRef<HTMLDivElement>(null);
    const scrollTop = scrollRef.current?.scrollTop ?? 0;

    const rulerTicks = useMemo(() => {
        const ticks: number[] = [];
        const step = model.windowDurationMs <= 100 ? 10 : model.windowDurationMs <= 500 ? 50 : 100;
        for (let t = 0; t <= model.windowDurationMs; t += step) {
            ticks.push(t);
        }
        return ticks;
    }, [model.windowDurationMs]);

    const selectedRow = model.rows.find(r => r.taskId === selectedTaskId) ?? null;

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
                <Box sx={{width: LABEL_WIDTH, flexShrink: 0}} />
                <Box sx={{flex: 1, position: 'relative', pr: 1}}>
                    {rulerTicks.map(tick => (
                        <Typography
                            key={tick}
                            variant="caption"
                            sx={{
                                position: 'absolute',
                                left: `${(tick / model.windowDurationMs) * 100}%`,
                                transform: 'translateX(-50%)',
                                fontSize: '0.65rem',
                                color: 'text.disabled',
                                top: 4,
                            }}
                        >
                            {formatRulerTick(tick)}
                        </Typography>
                    ))}
                </Box>
            </Box>

            <Box ref={scrollRef} sx={{flex: 1, overflow: 'auto', position: 'relative'}}>
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
                            model={model}
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
                                model={model}
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
