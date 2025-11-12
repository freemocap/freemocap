// LogTerminal.tsx
import {
    alpha,
    Box,
    Chip,
    Collapse,
    IconButton,
    TextField,
    ToggleButton,
    ToggleButtonGroup,
    Tooltip,
    useTheme,
} from "@mui/material";
import {useEffect, useRef, useState} from "react";
import {useAppDispatch, useAppSelector} from "@/store";
import {
    selectFilteredLogs,
    selectHasErrors,
    selectLogCountsByLevel,
    selectLogsPaused
} from "@/store/slices/log-records/logs-selectors";
import {logsCleared, logsFiltered, logsPaused} from "@/store/slices/log-records/log-records-slice";
import {LogRecord} from "@/store/slices/log-records/logs-types";
import {
    Delete as DeleteIcon,
    Pause as PauseIcon,
    PlayArrow as PlayArrowIcon,
    Search as SearchIcon,
    Warning as WarningIcon
} from "@mui/icons-material";

const LOG_COLORS = {
    TRACE: "#ccc",
    DEBUG: "#88ccFF",
    INFO: "#00E5FF",
    SUCCESS: "#FF66FF",
    API: "#66FF66",
    WARNING: "#FFFF66",
    ERROR: "#FF6666",
    CRITICAL: "#FF0000",
} as const;

const LogEntryComponent = ({ log }: { log: LogRecord }) => {
    const [expanded, setExpanded] = useState(false);
    const color =
        LOG_COLORS[log.levelname.toUpperCase() as keyof typeof LOG_COLORS] || "#ccc";
    const theme = useTheme();

    const renderWithFormatting = (text: string | null | undefined): React.ReactNode => {
        if (!text) return null;

        return text.split("\n").map((line, i) => (
            <div
                key={i}
                style={{
                    whiteSpace: "pre-wrap",
                    fontFamily: "monospace",
                    lineHeight: "1.2",
                }}
            >
                {line}
            </div>
        ));
    };

    return (
        <Box
            sx={{
                mb: 0.5,
                borderLeft: `2px solid ${color}`,
                pl: 1,
                backgroundColor: expanded
                    ? alpha(color, 0.1)
                    : theme.palette.mode === "dark"
                        ? "rgba(0,0,0,0.2)"
                        : "rgba(0,0,0,0.05)",
                cursor: "pointer",
                transition: "background-color 0.1s",
                "&:hover": {
                    backgroundColor: alpha(
                        color,
                        theme.palette.mode === "dark" ? 0.05 : 0.1
                    ),
                },
            }}
            onClick={() => setExpanded(!expanded)}
        >
            <Box sx={{ display: "flex", gap: 1, alignItems: "center", py: 0.5 }}>
                <span
                    style={{
                        color: theme.palette.mode === "dark" ? "#888" : "#555",
                        fontSize: "0.9em",
                        minWidth: "140px",
                    }}
                >
                    {log.asctime}
                </span>
                <Chip
                    size="small"
                    label={log.levelname}
                    sx={{
                        backgroundColor: color,
                        color: "#000",
                        height: 16,
                        fontSize: "0.8em",
                        minWidth: "60px",
                        ".MuiChip-label": {
                            px: 1,
                        },
                    }}
                />
                <span
                    style={{
                        color: theme.palette.mode === "dark" ? "#fff" : "#000",
                        flexGrow: 1,
                        fontSize: "0.9em",
                    }}
                >
                    {renderWithFormatting(log.message)}
                </span>
            </Box>

            <Collapse in={expanded}>
                <Box
                    sx={{
                        pl: 2,
                        py: 1,
                        fontSize: "0.8em",
                        color: theme.palette.mode === "dark" ? "#888" : "#555",
                        borderTop: "1px solid",
                        fontFamily: 'monospace',
                        borderColor:
                            theme.palette.mode === "dark"
                                ? "rgba(255,255,255,0.1)"
                                : "rgba(0,0,0,0.1)",
                    }}
                >
                    <div>
                        Location: {log.module}:{log.funcName}:Line#{log.lineno}
                    </div>
                    <div>File: {log.filename}</div>
                    <div>Time delta: {log.delta_t}</div>
                    <div>Path: {log.pathname}</div>
                    {log.formatted_message && (
                        <div>Raw message: {renderWithFormatting(log.formatted_message)}</div>
                    )}
                    <div>
                        Thread: {log.threadName} (ID: {log.thread})
                    </div>
                    <div>
                        Process: {log.processName} (ID: {log.process})
                    </div>

                    {(log.exc_info || log.exc_text) && (
                        <div>
                            <div>Exception details:</div>
                            {log.exc_info && <div>{renderWithFormatting(log.exc_info)}</div>}
                            {log.exc_text && <div>{renderWithFormatting(log.exc_text)}</div>}
                        </div>
                    )}

                    {log.stack_info && (
                        <div>
                            <div>Stack Trace:</div>
                            <pre
                                style={{
                                    whiteSpace: "pre-wrap",
                                    background:
                                        theme.palette.mode === "dark" ? "#111" : "#f5f5f5",
                                    padding: 8,
                                    borderRadius: 4,
                                    margin: "8px 0",
                                }}
                            >
                                {renderWithFormatting(log.stack_info)}
                            </pre>
                        </div>
                    )}
                </Box>
            </Collapse>
        </Box>
    );
};

export const LogTerminal = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();
    const logs = useAppSelector(selectFilteredLogs);
    const isPaused = useAppSelector(selectLogsPaused);
    const hasErrors = useAppSelector(selectHasErrors);
    const logCounts = useAppSelector(selectLogCountsByLevel);

    const [selectedLevels, setSelectedLevels] = useState<string[]>([]);
    const [searchText, setSearchText] = useState<string>("");
    const [showSearch, setShowSearch] = useState(false);
    const logEndRef = useRef<HTMLDivElement>(null);
    const shouldAutoScroll = useRef(true);

    // Update filter when levels or search text changes
    useEffect(() => {
        dispatch(logsFiltered({
            levels: selectedLevels,
            searchText: searchText
        }));
    }, [selectedLevels, searchText, dispatch]);

    // Auto-scroll to bottom when new logs arrive (if not paused)
    useEffect(() => {
        if (!isPaused && shouldAutoScroll.current) {
            logEndRef.current?.scrollIntoView({ behavior: "smooth" });
        }
    }, [logs, isPaused]);

    const handleLevelToggle = (_: React.MouseEvent<HTMLElement>, newLevels: string[]): void => {
        setSelectedLevels(newLevels);
    };

    const handlePauseToggle = (): void => {
        dispatch(logsPaused(!isPaused));
    };

    const handleClear = (): void => {
        dispatch(logsCleared());
    };

    const handleScroll = (e: React.UIEvent<HTMLDivElement>): void => {
        const element = e.currentTarget;
        const isAtBottom = element.scrollHeight - element.scrollTop <= element.clientHeight + 50;
        shouldAutoScroll.current = isAtBottom;
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
                    Server Logs
                </span>

                {hasErrors && (
                    <Tooltip title="Errors detected">
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
                        const count = logCounts[level] || 0;
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
                        <DeleteIcon fontSize="small" />
                    </IconButton>
                </Box>
            </Box>

            {showSearch && (
                <Box sx={{ p: 1, borderBottom: "1px solid", borderColor: theme.palette.divider }}>
                    <TextField
                        size="small"
                        fullWidth
                        placeholder="Search logs..."
                        value={searchText}
                        onChange={(e) => setSearchText(e.target.value)}
                        InputProps={{
                            startAdornment: <SearchIcon sx={{ mr: 1, color: "text.secondary" }} />,
                        }}
                    />
                </Box>
            )}

            <Box
                sx={{
                    flex: 1,
                    overflowY: "auto",
                    p: 1,
                    "&::-webkit-scrollbar": {
                        width: "8px",
                        backgroundColor: "transparent",
                    },
                    "&::-webkit-scrollbar-thumb": {
                        backgroundColor:
                            theme.palette.mode === "dark"
                                ? "rgba(255, 255, 255, 0.2)"
                                : "rgba(0, 0, 0, 0.2)",
                        borderRadius: "4px",
                        "&:hover": {
                            backgroundColor:
                                theme.palette.mode === "dark"
                                    ? "rgba(255, 255, 255, 0.3)"
                                    : "rgba(0, 0, 0, 0.3)",
                        },
                    },
                    "&::-webkit-scrollbar-track": {
                        backgroundColor: "transparent",
                    },
                    // For Firefox
                    scrollbarWidth: "thin",
                    scrollbarColor:
                        theme.palette.mode === "dark"
                            ? "rgba(255, 255, 255, 0.2) transparent"
                            : "rgba(0, 0, 0, 0.2) transparent",
                }}
                onScroll={handleScroll}
            >
                {logs.length === 0 ? (
                    <Box
                        sx={{
                            display: "flex",
                            justifyContent: "center",
                            alignItems: "center",
                            height: "100%",
                            color: theme.palette.text.disabled,
                        }}
                    >
                        {isPaused ? "Logging paused" : "No logs to display"}
                    </Box>
                ) : (
                    <>
                        {logs.map((log, i) => (
                            <LogEntryComponent key={`${log.created}-${log.thread}-${i}`} log={log} />
                        ))}
                        <div ref={logEndRef} />
                    </>
                )}
            </Box>
        </Box>
    );
};
