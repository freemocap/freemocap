import React, {useEffect, useRef, useState} from "react";
import {
    Alert,
    Box,
    Checkbox,
    Divider,
    FormControlLabel,
    FormGroup,
    IconButton,
    InputAdornment,
    Paper,
    Switch,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TableSortLabel,
    TextField,
    Typography,
} from "@mui/material";
import ClearIcon from "@mui/icons-material/Clear";
import SearchIcon from "@mui/icons-material/Search";
import {alpha, useTheme} from "@mui/material/styles";
import type {DetailedFramerate} from "@/services/server/server-helpers/framerate-store";
import {ProgressiveTooltip} from "@/components/framerate-viewer/FramerateStatisticsView";
import type {PipelineTimingSnapshot} from "@/services/server/server-helpers/pipeline-timing-store";
import {useTranslation} from "react-i18next";
import type {TFunction} from "i18next";
import {useServer} from "@/services/server/ServerContextProvider";
import {useAppDispatch, useAppSelector} from "@/store/hooks";
import {applyRealtimePipeline, selectIsPipelineConnected, selectPipelineConfig} from "@/store/slices/realtime";

const POLL_MS = 500;
const DIM_THRESHOLD_MS = 5000;

const METRIC_KEYS = ["recent", "mean", "median", "stdDev", "max", "min"] as const;
type MetricKey = typeof METRIC_KEYS[number];

function formatNumber(num: number | null, precision = 2): string {
    return num !== null ? num.toFixed(precision) : "N/A";
}

function computeCellValues(
    recentVal: number | null | undefined,
    aggregateData: DetailedFramerate | null,
): Record<MetricKey, {primary: string; secondary: string}> & {samples: string} {
    const safeFps = (durationMs: number | null | undefined): number | null =>
        durationMs !== null && durationMs !== undefined && durationMs > 0 ? 1000 / durationMs : null;

    return {
        recent: {
            primary: formatNumber(recentVal ?? null) + " ms",
            secondary: safeFps(recentVal ?? null) !== null ? formatNumber(safeFps(recentVal ?? null)) + " fps" : "—",
        },
        mean: {
            primary: formatNumber(aggregateData?.frame_duration_mean ?? null) + " ms",
            secondary: formatNumber(safeFps(aggregateData?.frame_duration_mean)) + " fps",
        },
        median: {
            primary: formatNumber(aggregateData?.frame_duration_median ?? null) + " ms",
            secondary: formatNumber(safeFps(aggregateData?.frame_duration_median)) + " fps",
        },
        stdDev: {
            primary: formatNumber(aggregateData?.frame_duration_stddev ?? null) + " ms",
            secondary: formatNumber(
                aggregateData ? aggregateData.frame_duration_coefficient_of_variation * 100 : null,
            ) + " CV%",
        },
        max: {
            primary: formatNumber(aggregateData?.frame_duration_max ?? null) + " ms",
            secondary: formatNumber(safeFps(aggregateData?.frame_duration_max)) + " fps",
        },
        min: {
            primary: formatNumber(aggregateData?.frame_duration_min ?? null) + " ms",
            secondary: formatNumber(safeFps(aggregateData?.frame_duration_min)) + " fps",
        },
        samples: String(aggregateData?.calculation_window_size || 0),
    };
}

/** Server-side preview path stages (recorded under `camera:<id>:…` in the timing store). */
const UI_BACKEND_CAMERA_STAGES = new Set([
    "jpeg_rotate_ms",
    "jpeg_resize_ms",
    "jpeg_encode_ms",
    "ws_payload_prepare_ms",
]);

type PipelineStatCategory = "capture" | "tracking" | "aggregation" | "ui_frontend" | "ui_backend" | "other";

/** Classify timing rows for the filter checkboxes. */
function pipelineStatRowCategory(rowKey: string): PipelineStatCategory {
    if (rowKey.startsWith("ui:")) {
        return "ui_frontend";
    }
    if (rowKey.startsWith("aggregator:")) {
        return "aggregation";
    }
    if (rowKey.startsWith("skeleton_inference:")) {
        return "tracking";
    }
    if (rowKey.startsWith("multiframe:")) {
        return "capture";
    }
    if (rowKey.startsWith("camera:")) {
        const stage = rowKey.split(":").slice(2).join(":");
        if (stage === "capture_to_aggregator_ms") {
            return "capture";
        }
        if (stage === "skeleton_detection" || stage === "charuco_detection") {
            return "tracking";
        }
        if (UI_BACKEND_CAMERA_STAGES.has(stage)) {
            return "ui_backend";
        }
        return "capture";
    }
    return "other";
}

function rowMatchesPipelineFilters(
    rowKey: string,
    filters: {
        capture: boolean;
        tracking: boolean;
        aggregation: boolean;
        ui_frontend: boolean;
        ui_backend: boolean;
    },
): boolean {
    const cat = pipelineStatRowCategory(rowKey);
    if (cat === "ui_frontend") return filters.ui_frontend;
    if (cat === "ui_backend") return filters.ui_backend;
    if (cat === "tracking") return filters.tracking;
    if (cat === "aggregation") return filters.aggregation;
    if (cat === "capture") return filters.capture;
    return filters.capture;
}

function rowPriority(key: string): number {
    if (key.startsWith("multiframe:")) return 0;
    if (key.startsWith("skeleton_inference:")) return 1;
    if (key.startsWith("aggregator:")) return 2;
    if (key.startsWith("camera:")) return 3;
    if (key.startsWith("ui:")) return 4;
    return 5;
}

function humanizeRowKey(rowKey: string): string {
    const pretty: Record<string, string> = {
        "multiframe:inter_camera_grab_spread_ms": "Inter-camera grab spread (multiframe)",
        "multiframe:ws_payload_prepare_ms": "WS payload prepare (multiframe)",
        "skeleton_inference:frame_read": "Skeleton GPU: frame read",
        "skeleton_inference:human_detection_preprocess": "Skeleton GPU: human detection preprocess",
        "skeleton_inference:human_detection": "Skeleton GPU: human detection",
        "skeleton_inference:human_detection_postprocess": "Skeleton GPU: human detection postprocess",
        "skeleton_inference:pose_estimation_preprocess": "Skeleton GPU: pose estimation preprocess",
        "skeleton_inference:pose_estimation": "Skeleton GPU: pose estimation",
        "skeleton_inference:pose_estimation_postprocess": "Skeleton GPU: pose estimation postprocess",
        "skeleton_inference:predict_batch": "Skeleton GPU: predict batch",
        "skeleton_inference:dropped_frames": "Skeleton GPU: dropped frames",
        "aggregator:capture_to_aggregator_ms": "Capture → aggregator",
        "aggregator:frame_collection_wait": "Frame collection wait",
        "aggregator:skeleton_triangulation": "Skeleton triangulation",
        "aggregator:charuco_triangulation": "Charuco triangulation",
        "aggregator:keypoint_filter": "Keypoint filter",
        "aggregator:velocity_gate": "Velocity gate",
        "aggregator:skeleton_filter": "Skeleton filter",
        "aggregator:full_frame_processing": "Full frame processing",
        "aggregator:loop_time": "Aggregator loop time",
        "camera:jpeg_encode_ms": "JPEG encode (server)",
        "camera:jpeg_resize_ms": "JPEG resize (server)",
        "camera:jpeg_rotate_ms": "JPEG rotate (server)",
        "camera:ws_payload_prepare_ms": "WS payload prepare (server)",
        "camera:grab_request_to_success_ms": "Grab request → success (camera)",
        "camera:retrieve_request_to_success_ms": "Retrieve request → success (camera)",
        "camera:cap_prop_pos_minus_perf_counter_ms": "Cam clock offset: CAP_POS_MSEC − pre-grab perf",
        "camera:skeleton_detection": "Skeleton detection",
        "camera:charuco_detection": "Charuco detection",
        "ui:jpeg_ack_to_receive_ms": "UI: ACK → JPEG received",
        "ui:jpeg_ws_binary_interval_ms": "UI: WS binary spacing",
        "ui:jpeg_ws_dispatch_lag_ms": "UI: WS binary handler lag",
        "ui:raf_body_before_decode_ms": "UI: rAF body before decode",
        "ui:jpeg_decode_worker_ms": "UI: JPEG decode (worker)",
        "ui:jpeg_decode_main_wait_ms": "UI: JPEG decode total wait",
        "ui:jpeg_decode_bridge_ms": "UI: JPEG decode bridge",
        "ui:main_dispatch_to_canvas_ms": "UI: dispatch → canvas worker",
        "ui:canvas_worker_receive_lag_ms": "UI: canvas worker receive lag",
        "ui:canvas_worker_raf_wait_ms": "UI: canvas worker rAF wait",
        "ui:canvas_bitmap_transfer_ms": "UI: bitmap transfer (worker)",
        "ui:render_ack_delivery_ms": "UI: render ack delivery",
        "ui:raf_to_rendered_ms": "UI: rAF tick → rendered",
    };
    if (pretty[rowKey]) return pretty[rowKey];
    if (rowKey.startsWith("aggregator:")) {
        const stage = rowKey.slice("aggregator:".length);
        return pretty[`aggregator:${stage}`] ?? stage;
    }
    if (rowKey.startsWith("skeleton_inference:")) {
        const stage = rowKey.slice("skeleton_inference:".length);
        return pretty[`skeleton_inference:${stage}`] ?? stage;
    }
    if (rowKey.startsWith("camera:")) {
        const parts = rowKey.split(":");
        const cam = parts[1];
        const stage = parts.slice(2).join(":");
        return `${cam} · ${pretty[`camera:${stage}`] ?? stage}`;
    }
    if (rowKey.startsWith("ui:")) {
        const parts = rowKey.split(":");
        const cam = parts[1];
        const stage = parts.slice(2).join(":");
        return `${cam} · ${pretty[`ui:${stage}`] ?? stage}`;
    }
    return rowKey.replace(/:/g, " · ");
}

/** Preferred display order for `ui:<camera>:<stage>` rows (then lexicographic by full key). */
const UI_TIMING_STAGE_ORDER: string[] = [
    "raf_body_before_decode_ms",
    "jpeg_decode_worker_ms",
    "jpeg_decode_main_wait_ms",
    "jpeg_decode_bridge_ms",
    "main_dispatch_to_canvas_ms",
    "canvas_worker_receive_lag_ms",
    "canvas_worker_raf_wait_ms",
    "canvas_bitmap_transfer_ms",
    "render_ack_delivery_ms",
    "raf_to_rendered_ms",
    "jpeg_ack_to_receive_ms",
    "jpeg_ws_binary_interval_ms",
    "jpeg_ws_dispatch_lag_ms",
];

function uiRowOrdinal(rowKey: string): number {
    if (!rowKey.startsWith("ui:")) return 10_000;
    const parts = rowKey.split(":");
    const stage = parts.slice(2).join(":");
    const i = UI_TIMING_STAGE_ORDER.indexOf(stage);
    return i === -1 ? 5000 : i;
}

function orderedRowKeys(aggregates: Map<string, DetailedFramerate | null>): string[] {
    const keys = Array.from(aggregates.keys());
    keys.sort(
        (a, b) =>
            rowPriority(a) - rowPriority(b)
            || uiRowOrdinal(a) - uiRowOrdinal(b)
            || a.localeCompare(b),
    );
    return keys;
}

/** Numeric ms (or CV for stdDev) used for sorting; null sorts last. */
function sortMetricValue(metric: MetricKey, rowKey: string, snap: PipelineTimingSnapshot): number | null {
    const agg = snap.aggregates.get(rowKey) ?? null;
    const recent = snap.recentValues.get(rowKey);
    switch (metric) {
        case "recent":
            return recent ?? null;
        case "mean":
            return agg?.frame_duration_mean ?? null;
        case "median":
            return agg?.frame_duration_median ?? null;
        case "stdDev":
            return agg?.frame_duration_stddev ?? null;
        case "max":
            return agg?.frame_duration_max ?? null;
        case "min":
            return agg?.frame_duration_min ?? null;
        default:
            return null;
    }
}

function compareNullableNumeric(a: number | null, b: number | null, direction: "asc" | "desc"): number {
    if (a === null && b === null) return 0;
    if (a === null) return 1;
    if (b === null) return -1;
    const cmp = a - b;
    return direction === "asc" ? cmp : -cmp;
}

/** Maps internal row keys to i18n suffix pipelineStages_row_<id>{Short,Long}. */
function pipelineStagesRowTooltipId(rowKey: string): string {
    const parts = rowKey.split(":");
    const head = parts[0];
    if (head === "aggregator") return `agg_${parts.slice(1).join("_")}`;
    if (head === "skeleton_inference") return `skel_${parts.slice(1).join("_")}`;
    if (head === "mediapipe_js") {
        if (parts.length >= 3) {
            return `mpjs_${parts.slice(2).join("_")}`;
        }
        return `mpjs_${parts.slice(1).join("_")}`;
    }
    if (head === "multiframe") return `mf_${parts.slice(1).join("_")}`;
    if (head === "camera") return `cam_${parts.slice(2).join("_")}`;
    if (head === "ui") return `ui_${parts.slice(2).join("_")}`;
    return `misc_${parts.join("_").replace(/:/g, "_")}`;
}

function getPipelineStageRowTooltip(rowKey: string, t: TFunction): { short: string; long: string } {
    const id = pipelineStagesRowTooltipId(rowKey);
    const shortKey = `pipelineStages_row_${id}Short`;
    const longKey = `pipelineStages_row_${id}Long`;
    const short = t(shortKey);
    const long = t(longKey);
    if (short === shortKey || long === longKey) {
        return {
            short: t("pipelineStages_row_unknownShort"),
            long: t("pipelineStages_row_unknownLong"),
        };
    }
    return {short, long};
}

function sortedRowKeys(
    baseKeys: string[],
    snap: PipelineTimingSnapshot,
    sortColumn: MetricKey | null,
    direction: "asc" | "desc",
): string[] {
    if (!sortColumn || baseKeys.length === 0) return baseKeys;
    return [...baseKeys].sort((a, b) => {
        const cmp = compareNullableNumeric(
            sortMetricValue(sortColumn, a, snap),
            sortMetricValue(sortColumn, b, snap),
            direction,
        );
        return cmp !== 0 ? cmp : a.localeCompare(b);
    });
}

type SortableMetricHeaderProps = {
    metric: MetricKey;
    label: string;
    shortInfo: string;
    longInfo: string;
    sortHint: string;
    sortColumn: MetricKey | null;
    sortDirection: "asc" | "desc";
    onSort: (metric: MetricKey) => void;
    headerCellStyle: Record<string, unknown>;
    cellStyle: Record<string, unknown>;
};

function SortableMetricHeader({
    metric,
    label,
    shortInfo,
    longInfo,
    sortHint,
    sortColumn,
    sortDirection,
    onSort,
    headerCellStyle,
    cellStyle,
}: SortableMetricHeaderProps): React.ReactElement {
    return (
        <ProgressiveTooltip
            shortInfo={`${shortInfo} ${sortHint}`}
            longInfo={longInfo}
        >
            <TableCell align="center" sx={{...headerCellStyle, ...cellStyle, cursor: "pointer", userSelect: "none"}}>
                <TableSortLabel
                    active={sortColumn === metric}
                    direction={sortColumn === metric ? sortDirection : "desc"}
                    onClick={() => onSort(metric)}
                    sx={{
                        fontSize: "0.65rem",
                        "& .MuiTableSortLabel-icon": {fontSize: "0.75rem"},
                    }}
                >
                    {label}
                </TableSortLabel>
            </TableCell>
        </ProgressiveTooltip>
    );
}

export default function PipelineStagesView(): React.ReactElement {
    const theme = useTheme();
    const isDarkMode = theme.palette.mode === "dark";
    const {t} = useTranslation();
    const {getPipelineTimingStore} = useServer();
    const dispatch = useAppDispatch();
    const pipelineConfig = useAppSelector(selectPipelineConfig);
    const pipelineConnected = useAppSelector(selectIsPipelineConnected);
    const logTimes = pipelineConfig.log_pipeline_times !== false;

    const spanRefs = useRef<Record<string, HTMLSpanElement | null>>({});
    const setSpanRef = (key: string) => (el: HTMLSpanElement | null) => {
        spanRefs.current[key] = el;
    };

    const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});
    const setRowRef = (key: string) => (el: HTMLTableRowElement | null) => {
        rowRefs.current[key] = el;
    };

    const [renderTick, setRenderTick] = useState(0);
    const [sortColumn, setSortColumn] = useState<MetricKey | null>(null);
    const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
    const [filterCapture, setFilterCapture] = useState(true);
    const [filterTracking, setFilterTracking] = useState(true);
    const [filterAggregation, setFilterAggregation] = useState(true);
    const [filterUiBackend, setFilterUiBackend] = useState(true);
    const [filterUiFrontend, setFilterUiFrontend] = useState(true);
    const [sourceFilterText, setSourceFilterText] = useState("");

    const handleMetricSort = (metric: MetricKey): void => {
        setSortColumn(prev => {
            if (prev !== metric) {
                setSortDirection("desc");
                return metric;
            }
            setSortDirection(d => (d === "desc" ? "asc" : "desc"));
            return metric;
        });
    };

    const handleResetRowOrder = (): void => {
        setSortColumn(null);
        setSortDirection("desc");
    };

    useEffect(() => {
        const tick = (): void => {
            const snapshot = getPipelineTimingStore().getSnapshot();
            const keys = orderedRowKeys(snapshot.aggregates);
            for (const rowKey of keys) {
                const agg = snapshot.aggregates.get(rowKey) ?? null;
                const recent = snapshot.recentValues.get(rowKey);
                const vals = computeCellValues(recent, agg);
                for (const metric of METRIC_KEYS) {
                    const pEl = spanRefs.current[`${rowKey}-${metric}-primary`];
                    if (pEl) pEl.textContent = vals[metric].primary;
                    const sEl = spanRefs.current[`${rowKey}-${metric}-secondary`];
                    if (sEl) sEl.textContent = vals[metric].secondary;
                }
                const samplesEl = spanRefs.current[`${rowKey}-samples`];
                if (samplesEl) samplesEl.textContent = `${vals.samples} ${t("samples")}`;

                const lastTs = snapshot.lastSampleTimestamps.get(rowKey);
                const rowEl = rowRefs.current[rowKey];
                if (rowEl) {
                    const stale = lastTs === undefined || Date.now() - lastTs > DIM_THRESHOLD_MS;
                    rowEl.style.opacity = stale ? "0.35" : "1";
                    rowEl.style.transition = "opacity 0.6s ease";
                }
            }
            setRenderTick(x => x + 1);
        };
        tick();
        const id = setInterval(tick, POLL_MS);
        return () => clearInterval(id);
    }, [getPipelineTimingStore, t]);

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

    void renderTick;
    const timingSnapshot = getPipelineTimingStore().getSnapshot();
    const baseRowKeys = orderedRowKeys(timingSnapshot.aggregates);
    const filterState = {
        capture: filterCapture,
        tracking: filterTracking,
        aggregation: filterAggregation,
        ui_frontend: filterUiFrontend,
        ui_backend: filterUiBackend,
    };
    const hasAnyFilter =
        filterCapture || filterTracking || filterAggregation || filterUiBackend || filterUiFrontend;
    const categoryFiltered = hasAnyFilter
        ? baseRowKeys.filter(k => rowMatchesPipelineFilters(k, filterState))
        : [];
    const trimmedSourceFilter = sourceFilterText.trim().toLowerCase();
    const filteredBase = trimmedSourceFilter.length === 0
        ? categoryFiltered
        : categoryFiltered.filter(k => {
            const label = humanizeRowKey(k).toLowerCase();
            return k.toLowerCase().includes(trimmedSourceFilter)
                || label.includes(trimmedSourceFilter);
        });
    const rowKeys = sortedRowKeys(filteredBase, timingSnapshot, sortColumn, sortDirection);
    const noRowsMatchCategoryFilter =
        hasAnyFilter && baseRowKeys.length > 0 && categoryFiltered.length === 0;
    const noRowsMatchTextFilter =
        hasAnyFilter
        && trimmedSourceFilter.length > 0
        && categoryFiltered.length > 0
        && filteredBase.length === 0;

    const handleToggleTiming = (_: unknown, checked: boolean): void => {
        dispatch(applyRealtimePipeline({
            ...pipelineConfig,
            log_pipeline_times: checked,
        }));
    };

    const sortHint = t("pipelineStages_sortHint");

    return (
        <Box sx={{display: "flex", flexDirection: "column", gap: 1, overflow: "auto", maxHeight: "100%"}}>
            {!pipelineConnected && (
                <Alert severity="info">Connect the realtime pipeline to collect pipeline stage timings.</Alert>
            )}
            {pipelineConnected && (
                <FormControlLabel
                    control={
                        <Switch
                            checked={logTimes}
                            onChange={handleToggleTiming}
                            size="small"
                        />
                    }
                    label={logTimes ? "Pipeline timing enabled" : "Enable pipeline timing (server + UI metrics)"}
                />
            )}
            {!logTimes && pipelineConnected && (
                <Alert severity="warning">
                    Timing is off — toggle above or apply pipeline with{" "}
                    <Typography component="span" variant="body2" fontFamily="monospace">log_pipeline_times</Typography>.
                </Alert>
            )}
            <Box>
                <Typography variant="caption" color="text.secondary" sx={{display: "block", mb: 0.5}}>
                    {t("pipelineStages_filterHeading")}
                </Typography>
                <FormGroup row sx={{flexWrap: "wrap", gap: 0.5, alignItems: "center"}}>
                    <ProgressiveTooltip
                        shortInfo={t("pipelineStages_filterCapture")}
                        longInfo={t("pipelineStages_filterCaptureLong")}
                    >
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={filterCapture}
                                    onChange={e => setFilterCapture(e.target.checked)}
                                    size="small"
                                />
                            }
                            label={<Typography variant="body2">{t("pipelineStages_filterCapture")}</Typography>}
                        />
                    </ProgressiveTooltip>
                    <ProgressiveTooltip
                        shortInfo={t("pipelineStages_filterUiBackend")}
                        longInfo={t("pipelineStages_filterUiBackendLong")}
                    >
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={filterUiBackend}
                                    onChange={e => setFilterUiBackend(e.target.checked)}
                                    size="small"
                                />
                            }
                            label={<Typography variant="body2">{t("pipelineStages_filterUiBackend")}</Typography>}
                        />
                    </ProgressiveTooltip>
                    <ProgressiveTooltip
                        shortInfo={t("pipelineStages_filterTracking")}
                        longInfo={t("pipelineStages_filterTrackingLong")}
                    >
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={filterTracking}
                                    onChange={e => setFilterTracking(e.target.checked)}
                                    size="small"
                                />
                            }
                            label={<Typography variant="body2">{t("pipelineStages_filterTracking")}</Typography>}
                        />
                    </ProgressiveTooltip>
                    <ProgressiveTooltip
                        shortInfo={t("pipelineStages_filterAggregation")}
                        longInfo={t("pipelineStages_filterAggregationLong")}
                    >
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={filterAggregation}
                                    onChange={e => setFilterAggregation(e.target.checked)}
                                    size="small"
                                />
                            }
                            label={<Typography variant="body2">{t("pipelineStages_filterAggregation")}</Typography>}
                        />
                    </ProgressiveTooltip>
                    <ProgressiveTooltip
                        shortInfo={t("pipelineStages_filterUiFrontend")}
                        longInfo={t("pipelineStages_filterUiFrontendLong")}
                    >
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={filterUiFrontend}
                                    onChange={e => setFilterUiFrontend(e.target.checked)}
                                    size="small"
                                />
                            }
                            label={<Typography variant="body2">{t("pipelineStages_filterUiFrontend")}</Typography>}
                        />
                    </ProgressiveTooltip>
                </FormGroup>
                <TextField
                    value={sourceFilterText}
                    onChange={e => setSourceFilterText(e.target.value)}
                    placeholder={t("pipelineStages_sourceTextFilterPlaceholder")}
                    size="small"
                    fullWidth
                    sx={{mt: 0.5}}
                    inputProps={{"aria-label": t("pipelineStages_sourceTextFilterAria")}}
                    InputProps={{
                        startAdornment: (
                            <InputAdornment position="start">
                                <SearchIcon fontSize="small" />
                            </InputAdornment>
                        ),
                        endAdornment: sourceFilterText ? (
                            <InputAdornment position="end">
                                <IconButton
                                    size="small"
                                    onClick={() => setSourceFilterText("")}
                                    aria-label="clear source filter"
                                >
                                    <ClearIcon fontSize="small" />
                                </IconButton>
                            </InputAdornment>
                        ) : null,
                    }}
                />
            </Box>
            <TableContainer component={Paper} elevation={0} sx={{backgroundColor: "transparent", border: "none"}}>
                <Table size="small" padding="none" sx={{"& .MuiTableCell-root": {fontSize: "0.65rem", lineHeight: "1.1"}}}>
                    <TableHead>
                        <TableRow>
                            <ProgressiveTooltip
                                shortInfo={t("pipelineStages_sourceShort")}
                                longInfo={t("pipelineStages_sourceLong")}
                            >
                                <TableCell
                                    align="left"
                                    onClick={handleResetRowOrder}
                                    sx={{
                                        ...headerCellStyle,
                                        width: "28%",
                                        color: theme.palette.text.primary,
                                        cursor: sortColumn ? "pointer" : "default",
                                        userSelect: "none",
                                    }}
                                >
                                    {t("source")}
                                    {sortColumn ? (
                                        <Typography component="span" variant="caption" color="text.secondary" sx={{display: "block", fontSize: "0.55rem"}}>
                                            {t("pipelineStages_restoreOrderHint")}
                                        </Typography>
                                    ) : null}
                                </TableCell>
                            </ProgressiveTooltip>
                            <SortableMetricHeader
                                metric="recent"
                                label={t("Recent")}
                                shortInfo={t("pipelineStages_col_recentShort")}
                                longInfo={t("pipelineStages_col_recentLong")}
                                sortHint={sortHint}
                                sortColumn={sortColumn}
                                sortDirection={sortDirection}
                                onSort={handleMetricSort}
                                headerCellStyle={headerCellStyle}
                                cellStyle={getCellStyle("recent")}
                            />
                            <SortableMetricHeader
                                metric="mean"
                                label={t("mean")}
                                shortInfo={t("pipelineStages_col_meanShort")}
                                longInfo={t("pipelineStages_col_meanLong")}
                                sortHint={sortHint}
                                sortColumn={sortColumn}
                                sortDirection={sortDirection}
                                onSort={handleMetricSort}
                                headerCellStyle={headerCellStyle}
                                cellStyle={getCellStyle("mean")}
                            />
                            <SortableMetricHeader
                                metric="median"
                                label={t("median")}
                                shortInfo={t("pipelineStages_col_medianShort")}
                                longInfo={t("pipelineStages_col_medianLong")}
                                sortHint={sortHint}
                                sortColumn={sortColumn}
                                sortDirection={sortDirection}
                                onSort={handleMetricSort}
                                headerCellStyle={headerCellStyle}
                                cellStyle={getCellStyle("median")}
                            />
                            <SortableMetricHeader
                                metric="stdDev"
                                label={t("stdDevCv")}
                                shortInfo={t("pipelineStages_col_stdDevShort")}
                                longInfo={t("pipelineStages_col_stdDevLong")}
                                sortHint={sortHint}
                                sortColumn={sortColumn}
                                sortDirection={sortDirection}
                                onSort={handleMetricSort}
                                headerCellStyle={headerCellStyle}
                                cellStyle={getCellStyle("stdDev")}
                            />
                            <SortableMetricHeader
                                metric="max"
                                label={t("max")}
                                shortInfo={t("pipelineStages_col_maxShort")}
                                longInfo={t("pipelineStages_col_maxLong")}
                                sortHint={sortHint}
                                sortColumn={sortColumn}
                                sortDirection={sortDirection}
                                onSort={handleMetricSort}
                                headerCellStyle={headerCellStyle}
                                cellStyle={getCellStyle("max")}
                            />
                            <SortableMetricHeader
                                metric="min"
                                label={t("min")}
                                shortInfo={t("pipelineStages_col_minShort")}
                                longInfo={t("pipelineStages_col_minLong")}
                                sortHint={sortHint}
                                sortColumn={sortColumn}
                                sortDirection={sortDirection}
                                onSort={handleMetricSort}
                                headerCellStyle={headerCellStyle}
                                cellStyle={getCellStyle("min")}
                            />
                        </TableRow>
                        <TableRow>
                            <TableCell colSpan={7} sx={{padding: 0}}><Divider /></TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {rowKeys.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={7}>
                                    <Typography variant="caption" color="text.secondary">
                                        {!hasAnyFilter
                                            ? t("pipelineStages_filterNoneSelected")
                                            : noRowsMatchCategoryFilter
                                                ? t("pipelineStages_filterEmptyResult")
                                                : noRowsMatchTextFilter
                                                    ? t("pipelineStages_filterEmptyResultText")
                                                    : t("pipelineStages_tableEmptyNoData")}
                                    </Typography>
                                </TableCell>
                            </TableRow>
                        ) : rowKeys.map((rowKey) => {
                            const rowTip = getPipelineStageRowTooltip(rowKey, t);
                            return (
                            <TableRow key={rowKey} ref={setRowRef(rowKey)}>
                                <TableCell
                                    sx={{fontWeight: "bold", paddingY: 0.5, maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis"}}
                                >
                                    <ProgressiveTooltip shortInfo={rowTip.short} longInfo={rowTip.long}>
                                        <Box component="span" sx={{display: "block", cursor: "help"}}>
                                            {humanizeRowKey(rowKey)}
                                            <Typography variant="caption" display="block" color="text.secondary" sx={{fontSize: "0.55rem"}}>
                                                <span ref={setSpanRef(`${rowKey}-samples`)}>—</span>
                                            </Typography>
                                        </Box>
                                    </ProgressiveTooltip>
                                </TableCell>
                                {METRIC_KEYS.map((metric) => (
                                    <TableCell key={metric} align="center" sx={getCellStyle(metric)}>
                                        <Typography fontWeight="bold" fontFamily="monospace" color={colorMap[metric]} sx={{fontSize: "0.7rem", whiteSpace: "nowrap"}}>
                                            <span ref={setSpanRef(`${rowKey}-${metric}-primary`)}>—</span>
                                        </Typography>
                                        <Typography variant="caption" color={colorMap[metric]} sx={{fontSize: "0.6rem", opacity: 0.9, whiteSpace: "nowrap"}}>
                                            <span ref={setSpanRef(`${rowKey}-${metric}-secondary`)}>—</span>
                                        </Typography>
                                    </TableCell>
                                ))}
                            </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    );
}
