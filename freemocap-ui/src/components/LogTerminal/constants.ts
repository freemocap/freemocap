export const LOG_POLL_INTERVAL_MS = 500;

/** Height of a single line of monospace text in the log view. */
export const LINE_HEIGHT = 20;

/** Vertical padding added to each log entry. */
export const ROW_PADDING = 8;

/** Extra rows rendered above/below the visible viewport. */
export const OVERSCAN = 10;

export const LOG_COLORS: Record<string, string> = {
    TRACE: "#ccc",
    DEBUG: "#88ccFF",
    INFO: "#00E5FF",
    SUCCESS: "#FF66FF",
    API: "#66FF66",
    WARNING: "#FFFF66",
    ERROR: "#FF6666",
    CRITICAL: "#FF0000",
};
