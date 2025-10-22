// logs-selectors.ts
import { createSelector } from '@reduxjs/toolkit';
import { RootState } from '../../types';
import { LogRecord } from './logs-types';

// Basic selectors
export const selectAllLogs = (state: RootState): LogRecord[] =>
    state.logs.entries;

export const selectLogsPaused = (state: RootState): boolean =>
    state.logs.isPaused;

export const selectLogsFilter = (state: RootState) =>
    state.logs.filter;

export const selectMaxLogEntries = (state: RootState): number =>
    state.logs.maxEntries;

// Filtered logs based on current filter settings
export const selectFilteredLogs = createSelector(
    [selectAllLogs, selectLogsFilter],
    (logs, filter) => {
        let filtered = logs;

        // Filter by levels if any are selected
        if (filter.levels.length > 0) {
            filtered = filtered.filter(log =>
                filter.levels.includes(log.levelname.toLowerCase())
            );
        }

        // Filter by search text if provided
        if (filter.searchText) {
            const searchLower = filter.searchText.toLowerCase();
            filtered = filtered.filter(log =>
                log.message.toLowerCase().includes(searchLower) ||
                log.module.toLowerCase().includes(searchLower) ||
                log.funcName.toLowerCase().includes(searchLower) ||
                log.formatted_message?.toLowerCase().includes(searchLower)
            );
        }

        return filtered;
    }
);

// Get logs by specific level
export const selectLogsByLevel = createSelector(
    [selectAllLogs, (_: RootState, level: string) => level],
    (logs, level) => logs.filter(log => log.levelname === level)
);

// Get recent logs (last N entries)
export const selectRecentLogs = createSelector(
    [selectAllLogs, (_: RootState, count: number = 10) => count],
    (logs, count) => logs.slice(-count)
);

// Get filtered recent logs
export const selectRecentFilteredLogs = createSelector(
    [selectFilteredLogs, (_: RootState, count: number = 10) => count],
    (logs, count) => logs.slice(-count)
);

// Count logs by level
export const selectLogCountsByLevel = createSelector(
    [selectAllLogs],
    (logs) => {
        const counts: Record<string, number> = {};
        logs.forEach(log => {
            const level = log.levelname;
            counts[level] = (counts[level] || 0) + 1;
        });
        return counts;
    }
);

// Get error and critical logs
export const selectErrorLogs = createSelector(
    [selectAllLogs],
    (logs) => logs.filter(log =>
        log.levelname === 'ERROR' || log.levelname === 'CRITICAL'
    )
);

// Check if there are any errors
export const selectHasErrors = createSelector(
    [selectErrorLogs],
    (errorLogs) => errorLogs.length > 0
);

// Get the most recent error
export const selectMostRecentError = createSelector(
    [selectErrorLogs],
    (errorLogs) => errorLogs[errorLogs.length - 1] || null
);
