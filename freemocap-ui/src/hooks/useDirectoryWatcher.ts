import {useCallback, useEffect, useRef, useState} from "react";

interface UseDirectoryWatcherResult {
    isWatching: boolean;
    lastChecked: Date | null;
    triggerRefresh: () => void;
}

/**
 * Polls a directory validation function on an interval.
 * Replaces manual "click refresh" patterns with automatic watching.
 */
export function useDirectoryWatcher(
    path: string | null,
    validateFn: (path: string) => Promise<void>,
    intervalMs = 3000,
): UseDirectoryWatcherResult {
    const [lastChecked, setLastChecked] = useState<Date | null>(null);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const doValidate = useCallback(async () => {
        if (!path) return;
        await validateFn(path);
        setLastChecked(new Date());
    }, [path, validateFn]);

    useEffect(() => {
        if (!path) {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
            }
            return;
        }

        // Initial check
        doValidate();

        intervalRef.current = setInterval(doValidate, intervalMs);

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
            }
        };
    }, [path, intervalMs, doValidate]);

    return {
        isWatching: !!path,
        lastChecked,
        triggerRefresh: doValidate,
    };
}
