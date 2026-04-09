// src/components/framerate-viewer/FramerateStatisticsView.tsx
import React, {useEffect, useRef, useState} from "react";
import {
    Box,
    Divider,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Tooltip,
    Typography,
} from "@mui/material";
import {alpha, useTheme} from "@mui/material/styles";
import {DetailedFramerate} from "@/services/server/server-helpers/framerate-store";
import {backendColor, frontendColor} from "@/components/framerate-viewer/FrameRateViewer";
import {useTranslation} from "react-i18next";
import {useServer} from "@/services/server/ServerContextProvider";

const STATS_POLL_INTERVAL_MS = 500;

type FramerateStatisticsViewProps = {
    compact?: boolean;
};

const formatNumber = (num: number | null, precision = 3): string => {
    return num !== null ? num.toFixed(precision) : "N/A";
};

// --- Progressive tooltip (renders once, state is local to tooltip interaction) ---

type ProgressiveTooltipProps = {
    shortInfo: string;
    longInfo: string;
    children: React.ReactElement;
};

export const ProgressiveTooltip = ({
    shortInfo,
    longInfo,
    children,
}: ProgressiveTooltipProps) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const theme = useTheme();
    const {t} = useTranslation();

    return (
        <Tooltip
            title={
                <Box onClick={(e) => { e.preventDefault(); setIsExpanded(!isExpanded); }} sx={{cursor: "pointer"}}>
                    <Typography variant="body2">
                        {isExpanded ? longInfo : shortInfo}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{display: "block", mt: 1, textAlign: "center"}}>
                        {isExpanded ? t("clickToShowLess") : t("clickToLearnMore")}
                    </Typography>
                </Box>
            }
            arrow
            placement="top"
            componentsProps={{
                tooltip: {
                    sx: {
                        backgroundColor: theme.palette.background.paper,
                        color: theme.palette.text.primary,
                        border: `1px solid ${theme.palette.divider}`,
                        boxShadow: theme.shadows[3],
                        maxWidth: isExpanded ? 500 : 300,
                        p: 1.5,
                    },
                },
            }}
        >
            {children}
        </Tooltip>
    );
};

type HeaderCellWithTooltipProps = {
    label: string;
    shortInfo: string;
    longInfo: string;
    style?: object;
    align?: "inherit" | "left" | "center" | "right" | "justify";
};

export const HeaderCellWithTooltip = ({
    label,
    shortInfo,
    longInfo,
    style = {},
    align = "center",
}: HeaderCellWithTooltipProps) => (
    <ProgressiveTooltip shortInfo={shortInfo} longInfo={longInfo}>
        <TableCell align={align} sx={style}>
            {label}
        </TableCell>
    </ProgressiveTooltip>
);

// --- Ref key types ---

const METRIC_KEYS = ["recent", "mean", "median", "stdDev", "max", "min"] as const;
type MetricKey = typeof METRIC_KEYS[number];
const ROW_KEYS = ["backend", "frontend"] as const;
type RowKey = typeof ROW_KEYS[number];
type RefKey = `${RowKey}-${MetricKey}-${"primary" | "secondary"}` | `${RowKey}-samples`;

// --- Extract display strings from store data ---

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

// --- Main component: renders MUI table once, updates numbers via refs ---

export default function FramerateStatisticsView({
    compact = false,
}: FramerateStatisticsViewProps) {
    const theme = useTheme();
    const isDarkMode = theme.palette.mode === "dark";
    const {t} = useTranslation();
    const {getFramerateStore} = useServer();

    const spanRefs = useRef<Record<string, HTMLSpanElement | null>>({});
    const setSpanRef = (key: RefKey) => (el: HTMLSpanElement | null) => {
        spanRefs.current[key] = el;
    };

    // Poll the store and write to DOM spans — zero React re-renders.
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

    // --- Static styles ---

    const colorMap: Record<string, string> = {
        recent: isDarkMode ? theme.palette.success.light : theme.palette.success.main,
        mean: isDarkMode ? theme.palette.warning.light : theme.palette.warning.main,
        median: isDarkMode ? theme.palette.warning.dark : theme.palette.warning.dark,
        stdDev: isDarkMode ? theme.palette.primary.light : theme.palette.primary.main,
        max: isDarkMode ? theme.palette.error.light : theme.palette.error.main,
        min: isDarkMode ? theme.palette.info.light : theme.palette.info.main,
    };

    const getCellStyle = (metricType: string) => ({
        backgroundColor: alpha(colorMap[metricType] || theme.palette.grey[500], isDarkMode ? 0.2 : 0.1),
        borderBottom: "none",
        padding: "2px 4px",
    });

    const headerCellStyle = {fontWeight: "bold", paddingY: 0.5};

    const tooltips = {
        source: {short: t("statsSourceShort"), long: t("statsSourceLong")},
        recent: {short: t("statsCurrentShort"), long: t("statsCurrentLong")},
        mean: {short: t("statsMeanShort"), long: t("statsMeanLong")},
        median: {short: t("statsMedianShort"), long: t("statsMedianLong")},
        stdDev: {short: t("statsStdDevShort"), long: t("statsStdDevLong")},
        max: {short: t("statsMaxShort"), long: t("statsMaxLong")},
        min: {short: t("statsMinShort"), long: t("statsMinLong")},
    };

    // --- Render helpers (called once at mount) ---

    const renderMetricCell = (rowKey: RowKey, metric: MetricKey) => (
        <TableCell key={metric} align="center" sx={getCellStyle(metric)}>
            <Typography fontWeight="bold" fontFamily="monospace" color={colorMap[metric]} sx={{fontSize: "0.7rem", whiteSpace: "nowrap"}}>
                <span ref={setSpanRef(`${rowKey}-${metric}-primary`)}>--</span>
            </Typography>
            <Typography variant="caption" color={colorMap[metric]} sx={{fontSize: "0.6rem", opacity: 0.9, whiteSpace: "nowrap"}}>
                <span ref={setSpanRef(`${rowKey}-${metric}-secondary`)}>--</span>
            </Typography>
        </TableCell>
    );

    const renderRow = (rowKey: RowKey, sourceColor: string, sourceLabel: string, shortTooltip: string, longTooltip: string) => (
        <TableRow key={rowKey}>
            <ProgressiveTooltip shortInfo={shortTooltip} longInfo={longTooltip}>
                <TableCell sx={{fontWeight: "bold", borderLeft: `4px solid ${sourceColor}`, backgroundColor: `${sourceColor}22`, paddingY: 0.5, paddingLeft: 1, color: sourceColor, cursor: "help"}}>
                    {sourceLabel}
                    <Typography variant="caption" display="block" color="text.secondary" sx={{fontSize: "0.6rem"}}>
                        <span ref={setSpanRef(`${rowKey}-samples`)}>--</span>
                    </Typography>
                </TableCell>
            </ProgressiveTooltip>
            {METRIC_KEYS.map((metric) => renderMetricCell(rowKey, metric))}
        </TableRow>
    );

    // --- Static MUI table (rendered once) ---

    return (
        <TableContainer component={Paper} elevation={0} sx={{backgroundColor: "transparent", border: "none", overflowX: "auto"}}>
            <Table size="small" padding="none" sx={{"& .MuiTableCell-root": {fontSize: "0.65rem", lineHeight: "1.1", whiteSpace: "nowrap"}}}>
                <TableHead>
                    <TableRow>
                        <HeaderCellWithTooltip label={t("source")} shortInfo={tooltips.source.short} longInfo={tooltips.source.long} style={{...headerCellStyle, width: "12%", color: theme.palette.text.primary}} align="left" />
                        <HeaderCellWithTooltip label={t("Recent")} shortInfo={tooltips.recent.short} longInfo={tooltips.recent.long} style={{...headerCellStyle, ...getCellStyle("recent")}} />
                        <HeaderCellWithTooltip label={t("mean")} shortInfo={tooltips.mean.short} longInfo={tooltips.mean.long} style={{...headerCellStyle, ...getCellStyle("mean")}} />
                        <HeaderCellWithTooltip label={t("median")} shortInfo={tooltips.median.short} longInfo={tooltips.median.long} style={{...headerCellStyle, ...getCellStyle("median")}} />
                        <HeaderCellWithTooltip label={t("stdDevCv")} shortInfo={tooltips.stdDev.short} longInfo={tooltips.stdDev.long} style={{...headerCellStyle, ...getCellStyle("stdDev")}} />
                        <HeaderCellWithTooltip label={t("max")} shortInfo={tooltips.max.short} longInfo={tooltips.max.long} style={{...headerCellStyle, ...getCellStyle("max")}} />
                        <HeaderCellWithTooltip label={t("min")} shortInfo={tooltips.min.short} longInfo={tooltips.min.long} style={{...headerCellStyle, ...getCellStyle("min")}} />
                    </TableRow>
                    <TableRow>
                        <TableCell colSpan={7} sx={{padding: 0}}><Divider sx={{borderColor: theme.palette.divider}} /></TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {renderRow("backend", backendColor, t("server"), t("capturesFramesFromCamera"), "Server represents the camera frame-grabbing performance. This is the true rate at which frames are pulled from the camera and saved during recording. This is the most important metric for recording quality and should remain stable even if display performance fluctuates.")}
                    <TableRow>
                        <TableCell colSpan={7} sx={{padding: 0}}><Divider sx={{borderColor: theme.palette.divider}} /></TableCell>
                    </TableRow>
                    {renderRow("frontend", frontendColor, t("display"), t("rendersReceivedFrames"), t("displayTooltipLong"))}
                </TableBody>
            </Table>
        </TableContainer>
    );
}
