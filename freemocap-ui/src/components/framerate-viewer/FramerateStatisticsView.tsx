// src/components/framerate-viewer/FramerateStatisticsView.tsx
import React, {useEffect, useRef, useState} from "react";
import {DetailedFramerate} from "@/services/server/server-helpers/framerate-store";
import {backendColor, frontendColor} from "@/components/framerate-viewer/FrameRateViewer";
import {useTranslation} from "react-i18next";
import {useServer} from "@/services/server/ServerContextProvider";

const STATS_POLL_INTERVAL_MS = 500;
const DIM_THRESHOLD_MS = 5000;

type FramerateStatisticsViewProps = {
    compact?: boolean;
};

const formatNumber = (num: number | null, precision = 3): string => {
    return num !== null ? num.toFixed(precision) : "N/A";
};

type ProgressiveTooltipProps = {
    shortInfo: string;
    longInfo: string;
    children: React.ReactElement;
    /** When true, show longInfo immediately (no click-to-expand). */
    alwaysShowLong?: boolean;
};

export const ProgressiveTooltip = ({
    shortInfo,
    longInfo,
    children,
    alwaysShowLong = false,
}: ProgressiveTooltipProps) => {
    const [isExpanded, setIsExpanded] = useState(false);

    return (
        <span
            title={isExpanded ? longInfo : shortInfo}
            onClick={() => setIsExpanded(v => !v)}
            style={{cursor: 'help'}}
        >
            {children}
        </span>
    );
};

type HeaderCellWithTooltipProps = {
    label: string;
    shortInfo: string;
    longInfo: string;
    style?: React.CSSProperties;
    align?: "left" | "center" | "right";
};

export const HeaderCellWithTooltip = ({
    label,
    shortInfo,
    longInfo,
    style = {},
    align = "center",
}: HeaderCellWithTooltipProps) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const {t} = useTranslation();

    return (
        <th
            title={isExpanded ? longInfo : shortInfo}
            style={{...style, textAlign: align, cursor: 'help', userSelect: 'none'}}
            onClick={() => setIsExpanded(v => !v)}
        >
            {label}
        </th>
    );
};

const METRIC_KEYS = ["recent", "mean", "median", "stdDev", "max", "min"] as const;
type MetricKey = typeof METRIC_KEYS[number];
const ROW_KEYS = ["backend", "frontend"] as const;
type RowKey = typeof ROW_KEYS[number];
type RefKey = `${RowKey}-${MetricKey}-${"primary" | "secondary"}` | `${RowKey}-samples`;

function computeCellValues(
    currentData: DetailedFramerate | null,
    aggregateData: DetailedFramerate | null,
): Record<MetricKey, {primary: string; secondary: string}> & {samples: string} {
    const safeFps = (durationMs: number | null | undefined): number | null =>
        durationMs !== null && durationMs !== undefined && durationMs > 0 ? 1000 / durationMs : null;

    return {
        recent: {
            primary: formatNumber(currentData?.mean_frames_per_second ?? null) + " fps",
            secondary: formatNumber(currentData?.mean_frame_duration_ms ?? null) + " ms",
        },
        mean: {
            primary: formatNumber(safeFps(aggregateData?.frame_duration_mean)) + " fps",
            secondary: formatNumber(aggregateData?.frame_duration_mean ?? null) + " ms",
        },
        median: {
            primary: formatNumber(safeFps(aggregateData?.frame_duration_median)) + " fps",
            secondary: formatNumber(aggregateData?.frame_duration_median ?? null) + " ms",
        },
        stdDev: {
            primary: formatNumber(aggregateData?.frame_duration_stddev ?? null) + " ms",
            secondary: formatNumber(aggregateData ? aggregateData.frame_duration_coefficient_of_variation * 100 : null) + " CV%",
        },
        max: {
            primary: formatNumber(safeFps(aggregateData?.frame_duration_min)) + " fps",
            secondary: formatNumber(aggregateData?.frame_duration_min ?? null) + " ms",
        },
        min: {
            primary: formatNumber(safeFps(aggregateData?.frame_duration_max)) + " fps",
            secondary: formatNumber(aggregateData?.frame_duration_max ?? null) + " ms",
        },
        samples: String(aggregateData?.calculation_window_size || 0),
    };
}

const colorMap: Record<string, string> = {
    recent: '#66bb6a',
    mean: '#ffa726',
    median: '#f57c00',
    stdDev: '#42a5f5',
    max: '#ef5350',
    min: '#29b6f6',
};

export default function FramerateStatisticsView({
    compact = false,
}: FramerateStatisticsViewProps) {
    const {t} = useTranslation();
    const {getFramerateStore} = useServer();

    const spanRefs = useRef<Record<string, HTMLSpanElement | null>>({});
    const setSpanRef = (key: RefKey) => (el: HTMLSpanElement | null) => {
        spanRefs.current[key] = el;
    };

    const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});
    const setRowRef = (key: RowKey) => (el: HTMLTableRowElement | null) => {
        rowRefs.current[key] = el;
    };

    useEffect(() => {
        const tick = () => {
            const snapshot = getFramerateStore().getSnapshot();
            const rows: [RowKey, DetailedFramerate | null, DetailedFramerate | null][] = [
                ["backend", snapshot.currentBackendFramerate, snapshot.aggregateBackendFramerate],
                ["frontend", snapshot.currentFrontendFramerate, snapshot.aggregateFrontendFramerate],
            ];

            for (const [rowKey, currentData, aggregateData] of rows) {
                const vals = computeCellValues(currentData, aggregateData);
                for (const metric of METRIC_KEYS) {
                    const pEl = spanRefs.current[`${rowKey}-${metric}-primary`];
                    if (pEl) pEl.textContent = vals[metric].primary;
                    const sEl = spanRefs.current[`${rowKey}-${metric}-secondary`];
                    if (sEl) sEl.textContent = vals[metric].secondary;
                }
                const samplesEl = spanRefs.current[`${rowKey}-samples`];
                if (samplesEl) samplesEl.textContent = `${vals.samples} ${t("samples")}`;

                const lastTs = rowKey === "backend"
                    ? snapshot.lastBackendSampleTimestamp
                    : snapshot.lastFrontendSampleTimestamp;
                const rowEl = rowRefs.current[rowKey];
                if (rowEl) {
                    const stale = lastTs === 0 || Date.now() - lastTs > DIM_THRESHOLD_MS;
                    rowEl.style.opacity = stale ? "0.35" : "1";
                    rowEl.style.transition = "opacity 0.6s ease";
                }
            }
        };
        tick();
        const id = setInterval(tick, STATS_POLL_INTERVAL_MS);
        return () => clearInterval(id);
    }, [getFramerateStore, t]);

    const tooltips = {
        source: {short: t("statsSourceShort"), long: t("statsSourceLong")},
        recent: {short: t("statsCurrentShort"), long: t("statsCurrentLong")},
        mean: {short: t("statsMeanShort"), long: t("statsMeanLong")},
        median: {short: t("statsMedianShort"), long: t("statsMedianLong")},
        stdDev: {short: t("statsStdDevShort"), long: t("statsStdDevLong")},
        max: {short: t("statsMaxShort"), long: t("statsMaxLong")},
        min: {short: t("statsMinShort"), long: t("statsMinLong")},
    };

    const cellStyle = (metric: string): React.CSSProperties => ({
        backgroundColor: colorMap[metric] ? colorMap[metric] + '22' : undefined,
        borderBottom: 'none',
        padding: '2px 4px',
        textAlign: 'center',
    });

    const renderMetricCell = (rowKey: RowKey, metric: MetricKey) => (
        <td key={metric} style={cellStyle(metric)}>
            <div>
                <span ref={setSpanRef(`${rowKey}-${metric}-primary`)}>--</span>
            </div>
            <div>
                <span ref={setSpanRef(`${rowKey}-${metric}-secondary`)}>--</span>
            </div>
        </td>
    );

    const renderRow = (rowKey: RowKey, sourceColor: string, sourceLabel: string, shortTooltip: string, longTooltip: string) => (
        <tr key={rowKey} ref={setRowRef(rowKey)}>
            <td
                title={shortTooltip}
                style={{fontWeight: '800', borderLeft: `4px solid ${sourceColor}`, backgroundColor: `${sourceColor}22`, padding: '2px 4px 2px 8px', color: sourceColor, cursor: 'help'}}
            >
                {sourceLabel}
                <div style={{color: 'var(--color-text-secondary)'}}>
                    <span ref={setSpanRef(`${rowKey}-samples`)}>--</span>
                </div>
            </td>
            {METRIC_KEYS.map((metric) => renderMetricCell(rowKey, metric))}
        </tr>
    );

    const thStyle: React.CSSProperties = {};

    return (
        <div className="overflow-x">
            <table className="w-full text sm" style={{}}>
                <thead>
                    <tr>
                        <HeaderCellWithTooltip label={t("source")} shortInfo={tooltips.source.short} longInfo={tooltips.source.long} style={{...thStyle, width: '12%', color: 'var(--color-text-primary)', textAlign: 'left'}} align="left" />
                        <HeaderCellWithTooltip label={t("Recent")} shortInfo={tooltips.recent.short} longInfo={tooltips.recent.long} style={{...thStyle, ...{backgroundColor: colorMap.recent + '22'}}} />
                        <HeaderCellWithTooltip label={t("mean")} shortInfo={tooltips.mean.short} longInfo={tooltips.mean.long} style={{...thStyle, ...{backgroundColor: colorMap.mean + '22'}}} />
                        <HeaderCellWithTooltip label={t("median")} shortInfo={tooltips.median.short} longInfo={tooltips.median.long} style={{...thStyle, ...{backgroundColor: colorMap.median + '22'}}} />
                        <HeaderCellWithTooltip label={t("stdDevCv")} shortInfo={tooltips.stdDev.short} longInfo={tooltips.stdDev.long} style={{...thStyle, ...{backgroundColor: colorMap.stdDev + '22'}}} />
                        <HeaderCellWithTooltip label={t("max")} shortInfo={tooltips.max.short} longInfo={tooltips.max.long} style={{...thStyle, ...{backgroundColor: colorMap.max + '22'}}} />
                        <HeaderCellWithTooltip label={t("min")} shortInfo={tooltips.min.short} longInfo={tooltips.min.long} style={{...thStyle, ...{backgroundColor: colorMap.min + '22'}}} />
                    </tr>
                    <tr>
                        <td colSpan={7} className="p-0">
                            <div style={{height: 1, backgroundColor: 'var(--color-border-secondary)', margin: '4px 0'}} />
                        </td>
                    </tr>
                </thead>
                <tbody>
                    {renderRow("backend", backendColor, t("server"), t("capturesFramesFromCamera"), "Server represents the camera frame-grabbing performance. This is the true rate at which frames are pulled from the camera and saved during recording. This is the most important metric for recording quality and should remain stable even if display performance fluctuates.")}
                    <tr>
                        <td colSpan={7} className="p-0">
                            <div style={{height: 1, backgroundColor: 'var(--color-border-secondary)', margin: '4px 0'}} />
                        </td>
                    </tr>
                    {renderRow("frontend", frontendColor, t("display"), t("rendersReceivedFrames"), t("displayTooltipLong"))}
                </tbody>
            </table>
        </div>
    );
}
