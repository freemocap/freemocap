import React, {memo, useMemo, useState} from 'react';
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

function hexToRgba(hex: string, opacity: number): string {
    if (!hex || !hex.startsWith('#')) return `rgba(128,128,128,${opacity})`;
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${opacity})`;
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
    const tooltipText = `${rowTip.long} (${durationLabel})`;

    return (
        <div
            onClick={onSelect}
            style={{
                display: 'flex',
                alignItems: 'center',
                height: ROW_HEIGHT,
                cursor: 'pointer',
                minWidth: 0,
                opacity: row.stale ? 0.4 : 1,
                backgroundColor: selected ? hexToRgba('#16ac13', 0.08) : 'transparent',
            }}
        >
            <div
                style={{
                    width: LABEL_WIDTH,
                    minWidth: LABEL_WIDTH,
                    maxWidth: LABEL_WIDTH,
                    flexShrink: 0,
                    overflow: 'hidden',
                    paddingLeft: 8,
                    paddingRight: 8,
                }}
            >
                <span
                    title={tooltipText}
                    style={{
                        display: 'block',
                        width: '100%',
                        fontSize: '0.7rem',
                        color: 'var(--gray-400)',
                        cursor: 'help',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                    }}
                >
                    {row.label}
                </span>
            </div>
            <div style={{flex: 1, position: 'relative', height: '100%', paddingRight: 8, minWidth: 0, overflow: 'hidden'}}>
                {parentSpan?.visible && (
                    <div
                        style={{
                            position: 'absolute',
                            top: 2,
                            bottom: 2,
                            left: `${parentSpan.leftPct}%`,
                            width: `${parentSpan.widthPct}%`,
                            borderLeft: `1px solid ${hexToRgba(color, 0.35)}`,
                            borderRight: `1px solid ${hexToRgba(color, 0.35)}`,
                            backgroundColor: hexToRgba(color, 0.08),
                            pointerEvents: 'none',
                        }}
                    />
                )}
                {visible && (
                    <div
                        title={tooltipText}
                        style={{
                            position: 'absolute',
                            top: 4,
                            bottom: 4,
                            left: `${leftPct}%`,
                            width: `${widthPct}%`,
                            minWidth: 2,
                            borderRadius: 4,
                            backgroundColor: color,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            overflow: 'hidden',
                        }}
                    >
                        {showDurationOnBar && (
                            <span
                                style={{
                                    fontSize: '0.6rem',
                                    fontWeight: 600,
                                    lineHeight: 1,
                                    color: '#ffffff',
                                    textShadow: '0 0 2px rgba(0,0,0,0.75)',
                                    pointerEvents: 'none',
                                    paddingLeft: 2,
                                    paddingRight: 2,
                                }}
                            >
                                {durationLabel}
                            </span>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
});

function SelectedRowDetails({row}: {row: TimelineRowView}): React.ReactElement {
    const {t} = useTranslation();
    const rowTip = getPipelineStageRowTooltip(row.sourceKey, t);
    return (
        <div className="text md" style={{color: 'var(--gray-400)'}}>
            <span style={{fontWeight: 600}}>{row.label}</span>
            {' · '}
            {row.durationMs.toFixed(2)} ms
            {row.stale ? ' · stale' : ''}
            <div className="text md" style={{color: 'var(--gray-400)', marginTop: 2}}>
                {rowTip.long}
            </div>
        </div>
    );
}

export function PipelineNetworkTimeline({model, selectedTaskId, onSelectTask}: Props): React.ReactElement {
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
        <div style={{display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0}}>
            <div
                style={{
                    display: 'flex',
                    height: RULER_HEIGHT,
                    borderBottom: '1px solid var(--gray-700)',
                    flexShrink: 0,
                }}
            >
                <div
                    style={{
                        width: LABEL_WIDTH,
                        flexShrink: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'flex-end',
                        gap: 2,
                        paddingRight: 4,
                    }}
                >
                    <IconButton icon="minus-icon" title={t('zoomOut')} onClick={zoomOut} />
                    <IconButton icon="plus-icon" title={t('zoomIn')} onClick={zoomIn} />
                    {isZoomed && (
                        <IconButton icon="back-icon" title={t('resetZoom')} onClick={resetZoom} />
                    )}
                </div>
                <div style={{flex: 1, position: 'relative', paddingRight: 8}}>
                    {rulerTicks.map(tick => (
                        <span
                            key={tick}
                            className="text md"
                            style={{
                                position: 'absolute',
                                left: `${(tick / visibleWindow.visibleDurationMs) * 100}%`,
                                transform: 'translateX(-50%)',
                                fontSize: '0.65rem',
                                color: 'var(--gray-500)',
                                top: 4,
                            }}
                        >
                            {formatRulerTick(tick + (visibleWindow.visibleStartMs - model.windowStartMs))}
                        </span>
                    ))}
                </div>
            </div>

            <div
                ref={containerRef as React.Ref<HTMLDivElement>}
                onScroll={event => setScrollTop(event.currentTarget.scrollTop)}
                style={{
                    flex: 1,
                    overflow: 'auto',
                    position: 'relative',
                    cursor: chartCursor,
                }}
                {...chartHandlers}
            >
                <TimelineLinks model={model} scrollTop={scrollTop} />
                {model.rows.length === 0 ? (
                    <div className="text md" style={{color: 'var(--gray-400)', padding: 8}}>
                        No pipeline task events in the current {model.frameStart != null ? `${model.frameEnd! - model.frameStart! + 1}-frame` : ''} window.
                        {model.paused ? ' (paused)' : ''}
                    </div>
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
                    <div style={{marginTop: 8, borderTop: `1px solid ${hexToRgba('#2e2e2e', 0.5)}`}}>
                        <span className="text md" style={{color: 'var(--gray-400)', padding: '4px 8px', display: 'block'}}>
                            Events without frame context
                        </span>
                        {model.orphanUiRows.map(row => (
                            <TimelineRow
                                key={row.taskId}
                                row={row}
                                visibleWindow={visibleWindow}
                                selected={row.taskId === selectedTaskId}
                                onSelect={() => onSelectTask(row.taskId === selectedTaskId ? null : row.taskId)}
                            />
                        ))}
                    </div>
                )}
            </div>

            {selectedRow && (
                <div style={{padding: 8, borderTop: '1px solid var(--gray-700)', flexShrink: 0}}>
                    <SelectedRowDetails row={selectedRow} />
                </div>
            )}
        </div>
    );
}
