import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useServer} from '@/services/server/ServerContextProvider';
import {LogSnapshot} from '@/services/server/server-helpers/log-store';
import {applyFilters} from './filtering';
import {buildPrefixHeights, findStartIndex} from './virtualization';
import {LOG_POLL_INTERVAL_MS, OVERSCAN} from './constants';

export interface LogTerminalState {
    // data
    snapshot: LogSnapshot;
    filteredLogs: ReturnType<typeof applyFilters>;
    prefixHeights: number[];
    totalHeight: number;
    // virtualization
    scrollContainerRef: React.RefObject<HTMLDivElement | null>;
    startIdx: number;
    endIdx: number;
    offsetY: number;
    // ui state
    isPaused: boolean;
    selectedLevels: string[];
    searchText: string;
    showSearch: boolean;
    copyFeedback: boolean;
    // actions
    handleScroll: () => void;
    scrollToBottom: () => void;
    handleCopyToClipboard: () => Promise<void>;
    handleSaveToDisk: () => void;
    handleLevelToggle: (e: React.MouseEvent<HTMLElement>, newLevels: string[]) => void;
    handlePauseToggle: () => void;
    handleClear: () => void;
    setSearchText: React.Dispatch<React.SetStateAction<string>>;
    setShowSearch: React.Dispatch<React.SetStateAction<boolean>>;
}

export function useLogTerminal(): LogTerminalState {
    const {getLogStore} = useServer();

    const [snapshot, setSnapshot] = useState<LogSnapshot>({
        entries: [],
        hasErrors: false,
        countsByLevel: {},
        version: 0,
    });
    const [isPaused, setIsPaused] = useState(false);
    const [selectedLevels, setSelectedLevels] = useState<string[]>([]);
    const [searchText, setSearchText] = useState('');
    const [showSearch, setShowSearch] = useState(false);
    const [copyFeedback, setCopyFeedback] = useState(false);

    // Virtualization state
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const [scrollTop, setScrollTop] = useState(0);
    const [containerHeight, setContainerHeight] = useState(0);
    const shouldAutoScroll = useRef(true);
    const lastVersionRef = useRef(-1);

    // Poll the mutable LogStore on a fixed interval.
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
    // Deferred via requestAnimationFrame so the DOM has painted the updated
    // totalHeight before we read scrollHeight, preventing a visible bounce.
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
        // Tight tolerance accounts for sub-pixel rounding while ensuring the
        // user must be truly at the bottom to re-engage auto-scroll.
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

    const formatLogsForExport = useCallback((): string => {
        return filteredLogs
            .map((log) => `[${log.asctime}] [${log.levelname}] ${log.module}:${log.funcName}:${log.lineno} - ${log.message}`)
            .join('\n');
    }, [filteredLogs]);

    const handleCopyToClipboard = useCallback(async () => {
        await navigator.clipboard.writeText(formatLogsForExport());
        setCopyFeedback(true);
        setTimeout(() => setCopyFeedback(false), 2000);
    }, [formatLogsForExport]);

    const handleSaveToDisk = useCallback(() => {
        const text = formatLogsForExport();
        const blob = new Blob([text], {type: 'text/plain'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `freemocap-logs-${new Date().toISOString().replace(/[:.]/g, '-')}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, [formatLogsForExport]);

    const handleLevelToggle = useCallback((_: React.MouseEvent<HTMLElement>, newLevels: string[]) => {
        setSelectedLevels(newLevels);
    }, []);

    const handlePauseToggle = useCallback(() => {
        setIsPaused((prev) => !prev);
    }, []);

    const handleClear = useCallback(() => {
        getLogStore().clear();
        setSelectedLevels([]);
        setSearchText('');
        setShowSearch(false);
        setIsPaused(false);
        lastVersionRef.current = -1;
        setSnapshot({entries: [], hasErrors: false, countsByLevel: {}, version: 0});
    }, [getLogStore]);

    // Compute visible row window
    const startIdx = Math.max(0, findStartIndex(prefixHeights, scrollTop) - OVERSCAN);
    const endScrollTop = scrollTop + containerHeight;
    const endIdx = Math.min(filteredLogs.length, findStartIndex(prefixHeights, endScrollTop) + 1 + OVERSCAN);
    const offsetY = prefixHeights[startIdx];

    return {
        snapshot,
        filteredLogs,
        prefixHeights,
        totalHeight,
        scrollContainerRef,
        startIdx,
        endIdx,
        offsetY,
        isPaused,
        selectedLevels,
        searchText,
        showSearch,
        copyFeedback,
        handleScroll,
        scrollToBottom,
        handleCopyToClipboard,
        handleSaveToDisk,
        handleLevelToggle,
        handlePauseToggle,
        handleClear,
        setSearchText,
        setShowSearch,
    };
}
