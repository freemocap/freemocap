// LogTerminal.tsx
import {
    alpha,
    Box,
    IconButton,
    TextField,
    ToggleButton,
    ToggleButtonGroup,
    Tooltip,
    useTheme,
} from "@mui/material";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useServer } from "@/services/server/ServerContextProvider";
import { LogRecord, LogSnapshot } from "@/services/server/server-helpers/log-store";
import {
    DeleteSweep as DeleteSweepIcon,
    Pause as PauseIcon,
    PlayArrow as PlayArrowIcon,
    Search as SearchIcon,
    Warning as WarningIcon,
    ContentCopy as ContentCopyIcon,
    Save as SaveIcon,
    SaveAlt as ScrollToBottomIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";

const LOG_POLL_INTERVAL_MS = 500;

/** Height of a single line of monospace text in the log view. */
const LINE_HEIGHT = 20;

/** Vertical padding added to each log entry. */
const ROW_PADDING = 8;

/** Extra rows rendered above/below the visible viewport. */
const OVERSCAN = 10;

const LOG_COLORS: Record<string, string> = {
    TRACE: "#ccc",
    DEBUG: "#88ccFF",
    INFO: "#00E5FF",
    SUCCESS: "#FF66FF",
    API: "#66FF66",
    WARNING: "#FFFF66",
    ERROR: "#FF6666",
    CRITICAL: "#FF0000",
};

// ---------------------------------------------------------------------------
// URL linkification — splits text on http/https URLs and renders them as
// clickable <a> tags. When split() is called with a capture group, matched
// segments land at odd indices, so i % 2 === 1 identifies URLs.
// ---------------------------------------------------------------------------

const URL_REGEX = /(https?:\/\/[^\s)"'>\]]+)/g;

const Linkify = ({ text }: { text: string }) => {
    const parts = text.split(URL_REGEX);
    if (parts.length === 1) return <>{text}</>;

    return (
        <>
            {parts.map((part, i) =>
                i % 2 === 1 ? (
                    <a
                        key={i}
                        href={part}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: "#58a6ff", textDecoration: "underline" }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        {part}
                    </a>
                ) : (
                    <span key={i}>{part}</span>
                )
            )}
        </>
    );
};

// ---------------------------------------------------------------------------
// Variable-height virtualization helpers.
// Each log entry's height depends on the number of lines in its message.
// Single-line messages get a compact row; multi-line messages expand to
// show every line, rendered with preserved whitespace like a real terminal.
// ---------------------------------------------------------------------------

/** Count lines in a message. A message with no newlines has 1 line. */
const countLines = (text: string): number => {
    if (!text) return 1;
    let count = 1;
    for (let i = 0; i < text.length; i++) {
        if (text[i] === "\n") count++;
    }
    return count;
};

/** Compute the pixel height of a log entry based on its line count. */
const getRowHeight = (log: LogRecord): number => {
    const lines = countLines(log.message);
    if (lines === 1) {
        // Single-line: one line of text + padding
        return LINE_HEIGHT + ROW_PADDING;
    }
    // Multi-line: header line + all message lines + padding
    return LINE_HEIGHT + lines * LINE_HEIGHT + ROW_PADDING;
};

/**
 * Build a prefix-sum array of cumulative heights for variable-height virtualization.
 * prefixHeights[i] = total height of rows 0..i-1 (the Y offset of row i).
 * prefixHeights[n] = total height of all rows.
 */
const buildPrefixHeights = (logs: LogRecord[]): number[] => {
    const prefixes = new Array<number>(logs.length + 1);
    prefixes[0] = 0;
    for (let i = 0; i < logs.length; i++) {
        prefixes[i + 1] = prefixes[i] + getRowHeight(logs[i]);
    }
    return prefixes;
};

/** Binary search for the first row whose bottom edge is past the given Y offset. */
const findStartIndex = (prefixHeights: number[], y: number): number => {
    let lo = 0;
    let hi = prefixHeights.length - 2;
    while (lo < hi) {
        const mid = (lo + hi) >>> 1;
        if (prefixHeights[mid + 1] <= y) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    return lo;
};

// ---------------------------------------------------------------------------
// Lightweight log entry — renders multi-line messages with preserved whitespace
// ---------------------------------------------------------------------------

const LogEntryRow = React.memo(({ log, style }: { log: LogRecord; style: React.CSSProperties }) => {
    const [expanded, setExpanded] = useState(false);
    const color = LOG_COLORS[log.levelname.toUpperCase()] || "#ccc";
    const multiLine = log.message.includes("\n");

    return (
        <div
            style={{
                ...style,
                borderLeft: `2px solid ${color}`,
                paddingLeft: 8,
                paddingTop: ROW_PADDING / 2,
                paddingBottom: ROW_PADDING / 2,
                backgroundColor: expanded ? `${color}1a` : "rgba(0,0,0,0.2)",
                cursor: "pointer",
                fontFamily: "monospace",
                fontSize: "0.85em",
                lineHeight: `${LINE_HEIGHT}px`,
                overflow: expanded ? "visible" : "hidden",
                position: "relative",
            }}
            onClick={() => setExpanded((prev) => !prev)}
        >
            {/* Header line: timestamp + level badge + first line (or entire message if single-line) */}
            <div style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                <span style={{ color: "#888", marginRight: 8, fontSize: "0.9em" }}>
                    {log.asctime}
                </span>
                <span
                    style={{
                        backgroundColor: color,
                        color: "#000",
                        padding: "1px 5px",
                        borderRadius: 2,
                        fontSize: "0.75em",
                        fontWeight: 600,
                        marginRight: 8,
                        display: "inline-block",
                        lineHeight: "normal",
                        verticalAlign: "middle",
                    }}
                >
                    {log.levelname}
                </span>
                <span style={{ color: "#fff" }}>
                    <Linkify text={multiLine ? log.message.split("\n")[0] : log.message} />
                </span>
            </div>

            {/* Multi-line message body: remaining lines rendered with preserved whitespace */}
            {multiLine && (
                <div
                    style={{
                        whiteSpace: "pre",
                        color: "#fff",
                        paddingLeft: 4,
                    }}
                >
                    <Linkify text={log.message.split("\n").slice(1).join("\n")} />
                </div>
            )}

            {/* Expanded overlay for log metadata (click to toggle) */}
            {expanded && (
                <div
                    style={{
                        position: "absolute",
                        top: "100%",
                        left: 0,
                        right: 0,
                        zIndex: 10,
                        backgroundColor: "#1a1a1a",
                        borderLeft: `2px solid ${color}`,
                        borderBottom: `1px solid ${color}`,
                        boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
                        overflow: "auto",
                        maxHeight: 400,
                    }}
                    onClick={(e) => e.stopPropagation()}
                >
                    <LogEntryDetail log={log} color={color} />
                </div>
            )}
        </div>
    );
});
LogEntryRow.displayName = "LogEntryRow";

const LogEntryDetail = ({ log, color }: { log: LogRecord; color: string }) => {
    const { t } = useTranslation();

    return (
        <div
            style={{
                paddingLeft: 16,
                paddingTop: 6,
                paddingBottom: 6,
                fontSize: "0.8em",
                color: "#888",
                borderTop: "1px solid rgba(255,255,255,0.1)",
                whiteSpace: "pre-wrap",
                lineHeight: "1.4",
                overflow: "visible",
            }}
            onClick={(e) => e.stopPropagation()}
        >
            <div>Location: {log.module}:{log.funcName}:Line#{log.lineno}</div>
            <div>{t("fileLabel")}: {log.filename}</div>
            <div>{t("timeDelta")}: {log.delta_t}</div>
            <div>{t("pathLabel")}: <Linkify text={log.pathname} /></div>
            {log.formatted_message && (
                <div>{t("rawMessage")}: <Linkify text={log.formatted_message} /></div>
            )}
            <div>Thread: {log.threadName} (ID: {log.thread})</div>
            <div>Process: {log.processName} (ID: {log.process})</div>
            {(log.exc_info || log.exc_text) && (
                <div>
                    <div>{t("exceptionDetails")}:</div>
                    {log.exc_info && <div><Linkify text={log.exc_info} /></div>}
                    {log.exc_text && <div><Linkify text={log.exc_text} /></div>}
                </div>
            )}
            {log.stack_info && (
                <div>
                    <div>{t("stackTrace")}:</div>
                    <pre
                        style={{
                            whiteSpace: "pre-wrap",
                            background: "#111",
                            padding: 8,
                            borderRadius: 4,
                            margin: "8px 0",
                        }}
                    >
                        <Linkify text={log.stack_info} />
                    </pre>
                </div>
            )}
        </div>
    );
};

// ---------------------------------------------------------------------------
// Filtering
// ---------------------------------------------------------------------------

function applyFilters(
    entries: LogRecord[],
    selectedLevels: string[],
    searchText: string,
): LogRecord[] {
    let filtered = entries;

    if (selectedLevels.length > 0) {
        filtered = filtered.filter(log =>
            selectedLevels.includes(log.levelname.toLowerCase())
        );
    }

    if (searchText) {
        const searchLower = searchText.toLowerCase();
        filtered = filtered.filter(log =>
            log.message.toLowerCase().includes(searchLower) ||
            log.module.toLowerCase().includes(searchLower) ||
            log.funcName.toLowerCase().includes(searchLower) ||
            log.formatted_message?.toLowerCase().includes(searchLower)
        );
    }

    return filtered;
}

// ---------------------------------------------------------------------------
// LogTerminal
// ---------------------------------------------------------------------------

export const LogTerminal = () => {
    const theme = useTheme();
    const { t } = useTranslation();
    const { getLogStore } = useServer();

    const [snapshot, setSnapshot] = useState<LogSnapshot>({
        entries: [],
        hasErrors: false,
        countsByLevel: {},
        version: 0,
    });

    const [isPaused, setIsPaused] = useState(false);
    const [selectedLevels, setSelectedLevels] = useState<string[]>([]);
    const [searchText, setSearchText] = useState<string>("");
    const [showSearch, setShowSearch] = useState(false);
    const [copyFeedback, setCopyFeedback] = useState(false);

    // Virtualization state
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const [scrollTop, setScrollTop] = useState(0);
    const [containerHeight, setContainerHeight] = useState(0);
    const shouldAutoScroll = useRef(true);

    /** Track last snapshot version so we skip no-op polls. */
    const lastVersionRef = useRef(-1);

    // Poll the mutable LogStore on a fixed interval.
    useEffect(() => {
        if (isPaused) return;

        const poll = () => {
            const snap = getLogStore().getSnapshot();
            // Skip setState entirely if nothing changed — avoids React reconciliation
            if (snap.version === lastVersionRef.current) return;
            lastVersionRef.current = snap.version;
            setSnapshot(snap);
        };

        // Immediate snapshot when unpausing
        poll();

        const interval = setInterval(poll, LOG_POLL_INTERVAL_MS);
        return () => clearInterval(interval);
    }, [getLogStore, isPaused]);

    const filteredLogs = applyFilters(snapshot.entries, selectedLevels, searchText);

    // Build prefix-sum height array for variable-height virtualization.
    // Recomputed when filteredLogs changes (memoized to avoid recalc on scroll).
    const prefixHeights = useMemo(() => buildPrefixHeights(filteredLogs), [filteredLogs]);
    const totalHeight = prefixHeights[filteredLogs.length] || 0;

    // Track container height via ResizeObserver
    useEffect(() => {
        const container = scrollContainerRef.current;
        if (!container) return;

        const observer = new ResizeObserver((entries) => {
            for (const entry of entries) {
                setContainerHeight(Math.round(entry.contentRect.height));
            }
        });
        observer.observe(container);
        return () => observer.disconnect();
    }, []);

    // Auto-scroll to bottom when new logs arrive.
    // Deferred via requestAnimationFrame so that the DOM has painted the
    // updated totalHeight before we read scrollHeight — without this, the
    // scroll position gets set against a stale (shorter) scrollHeight and
    // then snaps back once layout catches up, causing a visible bounce.
    useEffect(() => {
        if (!isPaused && shouldAutoScroll.current && scrollContainerRef.current) {
            requestAnimationFrame(() => {
                const el = scrollContainerRef.current;
                if (el) {
                    el.scrollTop = el.scrollHeight;
                }
            });
        }
    }, [filteredLogs, isPaused]);

    const handleScroll = useCallback(() => {
        const el = scrollContainerRef.current;
        if (!el) return;
        setScrollTop(el.scrollTop);
        // Tight tolerance (< 2px) accounts for sub-pixel rounding while
        // ensuring the user must be truly at the bottom to re-engage
        // auto-scroll. A large tolerance causes auto-scroll to stay active
        // when the user is trying to read entries near the bottom.
        const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 2;
        shouldAutoScroll.current = isAtBottom;
    }, []);

    const scrollToBottom = useCallback(() => {
        const el = scrollContainerRef.current;
        if (el) {
            el.scrollTop = el.scrollHeight;
            shouldAutoScroll.current = true;
        }
    }, []);

    // Compute visible row window using variable-height prefix sums
    const startIdx = Math.max(0, findStartIndex(prefixHeights, scrollTop) - OVERSCAN);
    const endScrollTop = scrollTop + containerHeight;
    const endIdx = Math.min(filteredLogs.length, findStartIndex(prefixHeights, endScrollTop) + 1 + OVERSCAN);
    const offsetY = prefixHeights[startIdx];

    const formatLogsForExport = useCallback((): string => {
        return filteredLogs.map((log) =>
            `[${log.asctime}] [${log.levelname}] ${log.module}:${log.funcName}:${log.lineno} - ${log.message}`
        ).join('\n');
    }, [filteredLogs]);

    const handleCopyToClipboard = useCallback(async () => {
        const text = formatLogsForExport();
        await navigator.clipboard.writeText(text);
        setCopyFeedback(true);
        setTimeout(() => setCopyFeedback(false), 2000);
    }, [formatLogsForExport]);

    const handleSaveToDisk = useCallback(() => {
        const text = formatLogsForExport();
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `freemocap-logs-${new Date().toISOString().replace(/[:.]/g, '-')}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, [formatLogsForExport]);

    const handleLevelToggle = (_: React.MouseEvent<HTMLElement>, newLevels: string[]): void => {
        setSelectedLevels(newLevels);
    };

    const handlePauseToggle = (): void => {
        setIsPaused(prev => !prev);
    };

    const handleClear = (): void => {
        getLogStore().clear();
        setSelectedLevels([]);
        setSearchText("");
        setShowSearch(false);
        setIsPaused(false);
        lastVersionRef.current = -1;
        setSnapshot({ entries: [], hasErrors: false, countsByLevel: {}, version: 0 });
    };

    return (
        <Box
            sx={{
                height: "100%",
                display: "flex",
                flexDirection: "column",
                backgroundColor:
                    theme.palette.mode === "dark" ? "#1a1a1a" : theme.palette.grey[100],
            }}
        >
            {/* Toolbar */}
            <Box
                sx={{
                    p: 0.5,
                    borderBottom: "1px solid",
                    borderColor: theme.palette.divider,
                    display: "flex",
                    gap: 1,
                    alignItems: "center",
                    flexWrap: "wrap",
                }}
            >
                <span
                    style={{
                        color: theme.palette.text.primary,
                        fontSize: "0.9em",
                        fontWeight: "bold",
                    }}
                >
                    {t('serverLogs')}
                </span>

                {snapshot.hasErrors && (
                    <Tooltip title={t("errorsDetected")}>
                        <WarningIcon
                            sx={{
                                color: LOG_COLORS.ERROR,
                                fontSize: "1.2em",
                                animation: "pulse 2s infinite",
                                "@keyframes pulse": {
                                    "0%, 100%": { opacity: 1 },
                                    "50%": { opacity: 0.5 },
                                },
                            }}
                        />
                    </Tooltip>
                )}

                <ToggleButtonGroup
                    size="small"
                    value={selectedLevels}
                    onChange={handleLevelToggle}
                    sx={{
                        ".MuiToggleButtonGroup-grouped": {
                            border: `1px solid ${theme.palette.divider} !important`,
                            mx: "1px",
                            "&:not(:first-of-type)": {
                                borderRadius: "2px",
                            },
                            "&:first-of-type": {
                                borderRadius: "2px",
                            },
                        },
                    }}
                >
                    {Object.entries(LOG_COLORS).map(([level, color]) => {
                        const count = snapshot.countsByLevel[level] || 0;
                        return (
                            <ToggleButton
                                key={level}
                                value={level.toLowerCase()}
                                sx={{
                                    py: 0.25,
                                    px: 1,
                                    minWidth: 0,
                                    fontSize: "0.75em",
                                    position: "relative",
                                    color: alpha(color, 0.7),
                                    "&.Mui-selected": {
                                        backgroundColor: alpha(color, 0.15),
                                        color: color,
                                        "&:hover": {
                                            backgroundColor: alpha(color, 0.2),
                                        },
                                    },
                                    "&:hover": {
                                        backgroundColor: alpha(color, 0.1),
                                    },
                                }}
                            >
                                {level}
                                {count > 0 && (
                                    <span
                                        style={{
                                            marginLeft: "4px",
                                            fontSize: "0.8em",
                                            opacity: 0.7,
                                        }}
                                    >
                                        ({count})
                                    </span>
                                )}
                            </ToggleButton>
                        );
                    })}
                </ToggleButtonGroup>

                <Box sx={{ ml: "auto", display: "flex", gap: 0.5 }}>
                    <Tooltip title={copyFeedback ? t("copied") : t("copyLogsToClipboard")}>
                        <IconButton
                            size="small"
                            onClick={handleCopyToClipboard}
                            sx={{ color: copyFeedback ? theme.palette.success.main : theme.palette.text.secondary }}
                        >
                            <ContentCopyIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>

                    <Tooltip title={t("saveLogsToFile")}>
                        <IconButton
                            size="small"
                            onClick={handleSaveToDisk}
                            sx={{ color: theme.palette.text.secondary }}
                        >
                            <SaveIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>

                    <Tooltip title="Scroll to bottom">
                        <IconButton
                            size="small"
                            onClick={scrollToBottom}
                            sx={{ color: theme.palette.text.secondary }}
                        >
                            <ScrollToBottomIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>

                    <IconButton
                        size="small"
                        onClick={() => setShowSearch(!showSearch)}
                        sx={{ color: theme.palette.text.secondary }}
                    >
                        <SearchIcon fontSize="small" />
                    </IconButton>

                    <IconButton
                        size="small"
                        onClick={handlePauseToggle}
                        sx={{
                            color: isPaused ? theme.palette.warning.main : theme.palette.text.secondary
                        }}
                    >
                        {isPaused ? <PlayArrowIcon fontSize="small" /> : <PauseIcon fontSize="small" />}
                    </IconButton>

                    <IconButton
                        size="small"
                        onClick={handleClear}
                        sx={{ color: theme.palette.text.secondary }}
                    >
                        <DeleteSweepIcon fontSize="small" />
                    </IconButton>
                </Box>
            </Box>

            {showSearch && (
                <Box sx={{ p: 1, borderBottom: "1px solid", borderColor: theme.palette.divider }}>
                    <TextField
                        size="small"
                        fullWidth
                        placeholder={t("searchLogs")}
                        value={searchText}
                        onChange={(e) => setSearchText(e.target.value)}
                        InputProps={{
                            startAdornment: <SearchIcon sx={{ mr: 1, color: "text.secondary" }} />,
                        }}
                    />
                </Box>
            )}

            {/* Virtualized log list */}
            <div
                ref={scrollContainerRef}
                onScroll={handleScroll}
                style={{
                    flex: 1,
                    overflowY: "auto",
                    overflowX: "auto",
                    position: "relative",
                    scrollbarWidth: "thin" as any,
                    scrollbarColor:
                        theme.palette.mode === "dark"
                            ? "rgba(255, 255, 255, 0.2) transparent"
                            : "rgba(0, 0, 0, 0.2) transparent",
                }}
            >
                {filteredLogs.length === 0 ? (
                    <div
                        style={{
                            display: "flex",
                            justifyContent: "center",
                            alignItems: "center",
                            height: "100%",
                            color: theme.palette.text.disabled,
                        }}
                    >
                        {isPaused ? t("loggingPaused") : t("noLogsToDisplay")}
                    </div>
                ) : (
                    // Outer div creates the full scrollable height
                    <div style={{ height: totalHeight, position: "relative" }}>
                        {/* Inner div is offset to the first visible row */}
                        <div
                            style={{
                                position: "absolute",
                                top: offsetY,
                                left: 0,
                                right: 0,
                            }}
                        >
                            {filteredLogs.slice(startIdx, endIdx).map((log, i) => {
                                const rowIdx = startIdx + i;
                                const rowHeight = prefixHeights[rowIdx + 1] - prefixHeights[rowIdx];
                                return (
                                    <LogEntryRow
                                        key={`${log.created}-${log.thread}-${rowIdx}`}
                                        log={log}
                                        style={{ height: rowHeight }}
                                    />
                                );
                            })}
                        </div>
                    </div>
                )}
            </div>
        </Box>
    );
};
