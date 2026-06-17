// LogTerminal.tsx
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { useServer } from "@/services/server/ServerContextProvider";
import { LogRecord, LogSnapshot } from "@/services/server/server-helpers/log-store";
import { useTranslation } from "react-i18next";
import ButtonSm from "@/components/ui-components/ButtonSm";

const LOG_POLL_INTERVAL_MS = 500;
const LINE_HEIGHT = 20;
const ROW_PADDING = 8;
const OVERSCAN = 10;

const LOG_LEVELS = ["TRACE", "DEBUG", "INFO", "SUCCESS", "API", "WARNING", "ERROR", "CRITICAL"];

// ---------------------------------------------------------------------------
// URL linkification
// ---------------------------------------------------------------------------

const URL_REGEX = /(https?:\/\/[^\s)"'>\]]+)/g;

const Linkify = ({ text }: { text: string }) => {
    const parts = text.split(URL_REGEX);
    if (parts.length === 1) return <>{text}</>;

    return (
        <>
            {parts.map((part, i) =>
                i % 2 === 1 ? (
                    <a key={i} href={part} target="_blank" rel="noopener noreferrer"
                        className="log-link" onClick={(e) => e.stopPropagation()}>
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
// Variable-height virtualization helpers
// ---------------------------------------------------------------------------

const countLines = (text: string): number => {
    if (!text) return 1;
    let count = 1;
    for (let i = 0; i < text.length; i++) {
        if (text[i] === "\n") count++;
    }
    return count;
};

const getRowHeight = (log: LogRecord): number => {
    const lines = countLines(log.message);
    if (lines === 1) return LINE_HEIGHT + ROW_PADDING;
    return LINE_HEIGHT + lines * LINE_HEIGHT + ROW_PADDING;
};

const buildPrefixHeights = (logs: LogRecord[]): number[] => {
    const prefixes = new Array<number>(logs.length + 1);
    prefixes[0] = 0;
    for (let i = 0; i < logs.length; i++) {
        prefixes[i + 1] = prefixes[i] + getRowHeight(logs[i]);
    }
    return prefixes;
};

const findStartIndex = (prefixHeights: number[], y: number): number => {
    let lo = 0;
    let hi = prefixHeights.length - 2;
    while (lo < hi) {
        const mid = (lo + hi) >>> 1;
        if (prefixHeights[mid + 1] <= y) lo = mid + 1;
        else hi = mid;
    }
    return lo;
};

// ---------------------------------------------------------------------------
// Log entry row
// ---------------------------------------------------------------------------

const LogEntryRow = React.memo(({ log, style }: { log: LogRecord; style: React.CSSProperties }) => {
    const [expanded, setExpanded] = useState(false);
    const level = log.levelname.toLowerCase();
    const multiLine = log.message.includes("\n");

    return (
        <div
            className={clsx("log-entry", level, expanded && "expanded")}
            style={style}
            onClick={() => setExpanded((prev) => !prev)}
        >
            <div className="log-entry-header">
                <span className="log-timestamp">{log.asctime}</span>
                <span className={clsx("log-level-badge", level)}>{log.levelname}</span>
                <span className="log-message-text">
                    <Linkify text={multiLine ? log.message.split("\n")[0] : log.message} />
                </span>
            </div>

            {multiLine && (
                <div className="log-multiline-body">
                    <Linkify text={log.message.split("\n").slice(1).join("\n")} />
                </div>
            )}

            {expanded && (
                <div className="log-entry-detail-overlay" onClick={(e) => e.stopPropagation()}>
                    <LogEntryDetail log={log} />
                </div>
            )}
        </div>
    );
});
LogEntryRow.displayName = "LogEntryRow";

const LogEntryDetail = ({ log }: { log: LogRecord }) => {
    const { t } = useTranslation();

    return (
        <div className="log-entry-detail" onClick={(e) => e.stopPropagation()}>
            <div className="log-entry-detail-message"><Linkify text={log.message} /></div>
            <div>Location: {log.module}:{log.funcName}:Line#{log.lineno}</div>
            <div>{t("fileLabel")}: {log.filename}</div>
            <div>{t("timeDelta")}: {log.delta_t}</div>
            <div>{t("pathLabel")}: <Linkify text={log.pathname} /></div>
            {log.formatted_message && <div>{t("rawMessage")}: <Linkify text={log.formatted_message} /></div>}
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
                    <pre className="log-stack-trace">
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

function applyFilters(entries: LogRecord[], selectedLevels: string[], searchText: string): LogRecord[] {
    let filtered = entries;
    if (selectedLevels.length > 0) {
        filtered = filtered.filter(log => selectedLevels.includes(log.levelname.toLowerCase()));
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
// Collapsed summary view
// ---------------------------------------------------------------------------

const LogCollapsedView = ({ getLogStore, selectedLevels }: { getLogStore: ReturnType<typeof useServer>["getLogStore"]; selectedLevels: string[] }) => {
    const { t } = useTranslation();
    const [lastEntry, setLastEntry] = useState<LogRecord | null>(null);
    const [logActive, setLogActive] = useState(false);
    const activityTimerRef = useRef<ReturnType<typeof setTimeout>>();
    const lastVersionRef = useRef(-1);

    useEffect(() => {
        const poll = () => {
            const snap = getLogStore().getSnapshot();
            if (snap.version !== lastVersionRef.current) {
                lastVersionRef.current = snap.version;
                setLogActive(true);
                if (activityTimerRef.current) clearTimeout(activityTimerRef.current);
                activityTimerRef.current = setTimeout(() => setLogActive(false), 2500);
            }
            const entries = snap.entries;
            const visible = selectedLevels.length > 0
                ? entries.filter(e => selectedLevels.includes(e.levelname.toLowerCase()))
                : entries;
            setLastEntry(visible.length > 0 ? visible[visible.length - 1] : null);
        };
        poll();
        const id = setInterval(poll, LOG_POLL_INTERVAL_MS);
        return () => {
            clearInterval(id);
            if (activityTimerRef.current) clearTimeout(activityTimerRef.current);
        };
    }, [getLogStore, selectedLevels]);

    if (!lastEntry) return (
        <div className="log-collapsed-summary flex items-center h-full gap-1">
            <p className="text bg text-gray">{t("serverLogs")}</p>
        </div>
    );

    const level = lastEntry.levelname.toLowerCase();
    const firstLine = lastEntry.message.split("\n")[0];

    return (
        <div className="log-collapsed-summary flex items-center h-full gap-1 overflow-hidden">
            <p className="text bg text-gray">{t("serverLogs")}</p>
            <span className={clsx("log-activity-dot", logActive && "active")} />
            <span className={clsx("log-level-badge", level)}>{lastEntry.levelname}</span>
            <span className="log-timestamp">{lastEntry.asctime}</span>
            <span className="log-message-text text-nowrap overflow-hidden" style={{ textOverflow: "ellipsis" }}>
                {firstLine}
            </span>
        </div>
    );
};

// ---------------------------------------------------------------------------
// LogTerminal (full view)
// ---------------------------------------------------------------------------

interface LogTerminalFullProps {
    selectedLevels: string[];
    setSelectedLevels: React.Dispatch<React.SetStateAction<string[]>>;
    searchText: string;
    setSearchText: React.Dispatch<React.SetStateAction<string>>;
    showSearch: boolean;
    setShowSearch: React.Dispatch<React.SetStateAction<boolean>>;
    isPaused: boolean;
    setIsPaused: React.Dispatch<React.SetStateAction<boolean>>;
}

const LogTerminalFull = ({
    selectedLevels,
    setSelectedLevels,
    searchText,
    setSearchText,
    showSearch,
    setShowSearch,
    isPaused,
    setIsPaused,
}: LogTerminalFullProps) => {
    const { t } = useTranslation();
    const { getLogStore } = useServer();

    const [snapshot, setSnapshot] = useState<LogSnapshot>({
        entries: [],
        hasErrors: false,
        countsByLevel: {},
        version: 0,
    });

    const [copyFeedback, setCopyFeedback] = useState(false);

    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const [scrollTop, setScrollTop] = useState(0);
    const [containerHeight, setContainerHeight] = useState(0);
    const shouldAutoScroll = useRef(true);
    const lastVersionRef = useRef(-1);

    useEffect(() => {
        if (isPaused) return;
        const poll = () => {
            const snap = getLogStore().getSnapshot();
            if (snap.version === lastVersionRef.current) return;
            lastVersionRef.current = snap.version;
            setSnapshot(snap);
        };
        poll();
        const interval = setInterval(poll, LOG_POLL_INTERVAL_MS);
        return () => clearInterval(interval);
    }, [getLogStore, isPaused]);

    const filteredLogs = applyFilters(snapshot.entries, selectedLevels, searchText);
    const prefixHeights = useMemo(() => buildPrefixHeights(filteredLogs), [filteredLogs]);
    const totalHeight = prefixHeights[filteredLogs.length] || 0;

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

    useEffect(() => {
        if (!isPaused && shouldAutoScroll.current && scrollContainerRef.current) {
            requestAnimationFrame(() => {
                const el = scrollContainerRef.current;
                if (el) el.scrollTop = el.scrollHeight;
            });
        }
    }, [filteredLogs, isPaused]);

    const handleScroll = useCallback(() => {
        const el = scrollContainerRef.current;
        if (!el) return;
        setScrollTop(el.scrollTop);
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

    const startIdx = Math.max(0, findStartIndex(prefixHeights, scrollTop) - OVERSCAN);
    const endIdx = Math.min(filteredLogs.length, findStartIndex(prefixHeights, scrollTop + containerHeight) + 1 + OVERSCAN);
    const offsetY = prefixHeights[startIdx];

    const formatLogsForExport = useCallback((): string => {
        return filteredLogs.map((log) =>
            `[${log.asctime}] [${log.levelname}] ${log.module}:${log.funcName}:${log.lineno} - ${log.message}`
        ).join('\n');
    }, [filteredLogs]);

    const handleCopyToClipboard = useCallback(async () => {
        await navigator.clipboard.writeText(formatLogsForExport());
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

    const toggleLevel = (level: string) => {
        setSelectedLevels(prev =>
            prev.includes(level) ? prev.filter(l => l !== level) : [...prev, level]
        );
    };

    const handleClear = () => {
        getLogStore().clear();
        setSelectedLevels(LOG_LEVELS.map(l => l.toLowerCase()));
        setSearchText("");
        setShowSearch(false);
        setIsPaused(false);
        lastVersionRef.current = -1;
        setSnapshot({ entries: [], hasErrors: false, countsByLevel: {}, version: 0 });
    };

    return (
        <div className="log-terminal">
            {/* Toolbar */}
            <div className="log-toolbar flex items-center gap-1 p-1 flex-wrap">
                <div className="ml-1 log-toolbar-inner flex items-center gap-1 flex-wrap">
                    <p className="text bg text-gray">{t('serverLogs')}</p>
                    {snapshot.hasErrors && (
                        <span className="icon warning-icon icon-size-20" title={t("errorsDetected")} />
                    )}
                    {/* Level filter buttons */}
                    <div className="flex gap-1 flex-wrap">
                        {LOG_LEVELS.map((level) => {
                            const count = snapshot.countsByLevel[level] || 0;
                            const isActive = selectedLevels.includes(level.toLowerCase());
                            return (
                                <button
                                    key={level}
                                    className={clsx("button sm br-1 log-level-filter", level.toLowerCase(), isActive && "active")}
                                    onClick={() => toggleLevel(level.toLowerCase())}
                                >
                                    <p className="text sm">{level}{count > 0 ? ` (${count})` : ''}</p>
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Action buttons */}
                <div className="log-actions flex gap-1">
                    <ButtonSm
                        text={copyFeedback ? "" : ""}
                        iconClass={copyFeedback ? "copied-icon" : "copy-icon"}
                        textColor="text-gray"
                        onClick={handleCopyToClipboard}
                        tooltip={true}
                        tooltipText={copyFeedback ? "Copied!" : "Copy to clipboard"}
                        tooltipPosition="pos-bottom"
                    />
                    <ButtonSm
                        text=""
                        iconClass="save-icon"
                        textColor="text-gray"
                        onClick={handleSaveToDisk}
                        tooltip={true}
                        tooltipText="Save"
                        tooltipPosition="pos-bottom"
                    />
                    <ButtonSm
                        text=""
                        iconClass="scrolldown-icon"
                        textColor="text-gray"
                        onClick={scrollToBottom}
                        tooltip={true}
                        tooltipText="Scroll to bottom"
                        tooltipPosition="pos-bottom"
                    />
                    <ButtonSm
                        text=""
                        iconClass="search-icon"
                        textColor={showSearch ? "text-white" : "text-gray"}
                        buttonType={showSearch ? "activated" : ""}
                        onClick={() => setShowSearch(!showSearch)}
                        tooltip={true}
                        tooltipText="Search"
                        tooltipPosition="pos-bottom"
                    />
                    <ButtonSm
                        text=""
                        iconClass={isPaused ? "play-icon" : "pause-icon"}
                        textColor={isPaused ? "text-warning" : "text-gray"}
                        onClick={() => setIsPaused(prev => !prev)}
                        tooltip={true}
                        tooltipText={isPaused ? "Resume" : "Pause"}
                        tooltipPosition="pos-bottom"
                    />
                    <ButtonSm
                        text=""
                        iconClass="clear-icon"
                        textColor="text-gray"
                        onClick={handleClear}
                        tooltip={true}
                        tooltipText="Clear"
                        tooltipPosition="pos-bottom"
                    />
                </div>
            </div>

            {/* Search bar */}
            {showSearch && (
                <div className="log-search-bar p-1">
                    <div className="input-with-string w-full">
                        <input
                            className="input-field"
                            placeholder={t("searchLogs")}
                            value={searchText}
                            onChange={(e) => setSearchText(e.target.value)}
                            autoFocus
                        />
                    </div>
                </div>
            )}

            {/* Virtualized log list */}
            <div ref={scrollContainerRef} onScroll={handleScroll} className="log-scroll-area">
                {filteredLogs.length === 0 ? (
                    <div className="log-empty-state">
                        {isPaused ? t("loggingPaused") : t("noLogsToDisplay")}
                    </div>
                ) : (
                    <div className="log-virtual-track" style={{ height: totalHeight }}>
                        <div className="log-virtual-window" style={{ top: offsetY }}>
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
        </div>
    );
};

export const LogTerminal = ({ isCollapsed = false }: { isCollapsed?: boolean }) => {
    const { getLogStore } = useServer();
    const [selectedLevels, setSelectedLevels] = useState<string[]>(LOG_LEVELS.map(l => l.toLowerCase()));
    const [searchText, setSearchText] = useState("");
    const [showSearch, setShowSearch] = useState(false);
    const [isPaused, setIsPaused] = useState(false);

    if (isCollapsed) return (
        <LogCollapsedView getLogStore={getLogStore} selectedLevels={selectedLevels} />
    );
    return (
        <LogTerminalFull
            selectedLevels={selectedLevels} setSelectedLevels={setSelectedLevels}
            searchText={searchText} setSearchText={setSearchText}
            showSearch={showSearch} setShowSearch={setShowSearch}
            isPaused={isPaused} setIsPaused={setIsPaused}
        />
    );
};
