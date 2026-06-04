// src/components/framerate-viewer/FramerateStatisticsView.tsx
import React, {useEffect, useRef} from "react";
import {DetailedFramerate} from "@/services/server/server-helpers/framerate-store";
import {frontendColor, backendColor} from "@/components/framerate-viewer/FrameRateViewer";
import {useTranslation} from "react-i18next";
import {useServer} from "@/services/server/ServerContextProvider";

const STATS_POLL_INTERVAL_MS = 500;

type FramerateStatisticsViewProps = {
    compact?: boolean;
};

const formatNumber = (num: number | null, precision = 3): string => {
    return num !== null ? num.toFixed(precision) : "N/A";
};

const METRIC_KEYS = ["recent", "mean", "median", "stdDev", "max", "min"] as const;
type MetricKey = typeof METRIC_KEYS[number];
const ROW_KEYS = ["backend", "frontend"] as const;
type RowKey = typeof ROW_KEYS[number];
type RefKey = `${RowKey}-${MetricKey}-${"primary" | "secondary"}` | `${RowKey}-samples`;

// CSS class suffix per metric key (stdDev → stddev for valid class names)
const metricClass = (metric: MetricKey) => metric === "stdDev" ? "stddev" : metric;

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

export default function FramerateStatisticsView({compact = false}: FramerateStatisticsViewProps) {
    const {t} = useTranslation();
    const {getFramerateStore} = useServer();

    const spanRefs = useRef<Record<string, HTMLSpanElement | null>>({});
    const setSpanRef = (key: RefKey) => (el: HTMLSpanElement | null) => {
        spanRefs.current[key] = el;
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

    const renderTooltip = (text: string, position: string = "pos-bottom") => (
        <div className={`tooltip-container elevated-sharp ${position} p-01 br-2 bg-dark stats-tooltip`}>
            <div className="tooltip-inner br-1 pl-2 pr-2 pt-1 pb-1 border-1 border-mid-black border-solid">
                <span className="text-xs">{text}</span>
            </div>
        </div>
    );

    const renderMetricCell = (rowKey: RowKey, metric: MetricKey) => (
        <td key={metric} className={`stats-td stats-col-${metricClass(metric)}`}>
            <div className={`stats-cell-primary stats-cell-${metricClass(metric)}-text`}>
                <span ref={setSpanRef(`${rowKey}-${metric}-primary`)}>--</span>
            </div>
            <div className={`stats-cell-secondary stats-cell-${metricClass(metric)}-text`}>
                <span ref={setSpanRef(`${rowKey}-${metric}-secondary`)}>--</span>
            </div>
        </td>
    );

    const renderRow = (rowKey: RowKey, sourceLabel: string, tooltip: string) => (
        <tr key={rowKey}>
            <td className={`stats-td stats-source-cell stats-source-${rowKey}`}>
                {sourceLabel}
                <div className="stats-source-samples">
                    <span ref={setSpanRef(`${rowKey}-samples`)}>--</span>
                </div>
                {renderTooltip(tooltip, "pos-bottom-left")}
            </td>
            {METRIC_KEYS.map((metric) => renderMetricCell(rowKey, metric))}
        </tr>
    );

    return (
        <div className="stats-table-wrapper">
            <table className="stats-table">
                <thead>
                    <tr>
                        <th className="stats-th stats-th-source">
                            {t("source")}
                            {renderTooltip(`${tooltips.source.short} ${tooltips.source.long}`, "pos-bottom-left")}
                        </th>
                        {METRIC_KEYS.map((metric) => (
                            <th key={metric}
                                className={`stats-th stats-col-${metricClass(metric)}`}>
                                {t(metric === "stdDev" ? "stdDevCv" : metric === "recent" ? "Recent" : metric)}
                                {renderTooltip(`${tooltips[metric].short} ${tooltips[metric].long}`, (metric === "recent") ? "pos-bottom-left" : (metric === "stdDev" || metric === "max" || metric === "min") ? "pos-bottom-right" : "pos-bottom")}
                            </th>
                        ))}
                    </tr>
                    <tr className="stats-divider"><td colSpan={7} /></tr>
                </thead>
                <tbody>
                    {renderRow("backend", t("server"), t("capturesFramesFromCamera"))}
                    <tr className="stats-divider"><td colSpan={7} /></tr>
                    {renderRow("frontend", t("display"), t("rendersReceivedFrames"))}
                </tbody>
            </table>
        </div>
    );
}
