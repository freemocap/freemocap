// log-records-slice.ts
import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { LogRecord } from './logs-types';

interface LogRecordsState {
    entries: LogRecord[];
    maxEntries: number;
    isPaused: boolean;
    filter: {
        levels: string[];
        searchText: string;
    };
}

const initialState: LogRecordsState = {
    entries: [],
    maxEntries: 1000,
    isPaused: false,
    filter: {
        levels: [],
        searchText: '',
    },
};

export const logRecordsSlice = createSlice({
    name: 'logs',
    initialState,
    reducers: {
        logAdded: (state, action: PayloadAction<LogRecord>) => {
            if (state.isPaused) return;

            state.entries.push(action.payload);

            // Keep only the last maxEntries
            if (state.entries.length > state.maxEntries) {
                state.entries = state.entries.slice(-state.maxEntries);
            }
        },

        logsAdded: (state, action: PayloadAction<LogRecord[]>) => {
            if (state.isPaused) return;

            state.entries.push(...action.payload);

            // Keep only the last maxEntries
            if (state.entries.length > state.maxEntries) {
                state.entries = state.entries.slice(-state.maxEntries);
            }
        },

        logsCleared: (state) => {
            state.entries = [];
        },

        logsPaused: (state, action: PayloadAction<boolean>) => {
            state.isPaused = action.payload;
        },

        logsFiltered: (state, action: PayloadAction<{ levels?: string[]; searchText?: string }>) => {
            if (action.payload.levels !== undefined) {
                state.filter.levels = action.payload.levels;
            }
            if (action.payload.searchText !== undefined) {
                state.filter.searchText = action.payload.searchText;
            }
        },

        maxEntriesUpdated: (state, action: PayloadAction<number>) => {
            state.maxEntries = action.payload;

            // Trim entries if new max is smaller
            if (state.entries.length > action.payload) {
                state.entries = state.entries.slice(-action.payload);
            }
        },
    },
});

export const {
    logAdded,
    logsAdded,
    logsCleared,
    logsPaused,
    logsFiltered,
    maxEntriesUpdated
} = logRecordsSlice.actions;
