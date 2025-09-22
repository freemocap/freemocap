// framerate-slice.ts
import {createSlice, type PayloadAction} from '@reduxjs/toolkit';

interface FramerateData {
    mean: number;
    std: number;
    current: number;
}

interface FramerateState {
    backend: FramerateData | null;
    frontend: FramerateData | null;
    // Add arrays for historical data if you want to calculate averages
    recentFrontendFrameDurations: number[];
    recentBackendFrameDurations: number[];
}

const initialState: FramerateState = {
    backend: null,
    frontend: null,
    recentFrontendFrameDurations: [],
    recentBackendFrameDurations: [],
};

const MAX_DURATION_HISTORY = 100; // Keep last 100 frame durations

export const framerateSlice = createSlice({
    name: 'framerate',
    initialState,
    reducers: {
        backendFramerateUpdated: (state, action: PayloadAction<FramerateData>) => {
            state.backend = action.payload;
            // If current framerate exists, calculate duration and add to history
            if (action.payload.current > 0) {
                const duration = 1000 / action.payload.current; // Convert FPS to ms
                state.recentBackendFrameDurations = [
                    ...state.recentBackendFrameDurations.slice(-(MAX_DURATION_HISTORY - 1)),
                    duration
                ];
            }
        },
        frontendFramerateUpdated: (state, action: PayloadAction<FramerateData>) => {
            state.frontend = action.payload;
            // If current framerate exists, calculate duration and add to history
            if (action.payload.current > 0) {
                const duration = 1000 / action.payload.current; // Convert FPS to ms
                state.recentFrontendFrameDurations = [
                    ...state.recentFrontendFrameDurations.slice(-(MAX_DURATION_HISTORY - 1)),
                    duration
                ];
            }
        },
        clearFramerateHistory: (state) => {
            state.recentFrontendFrameDurations = [];
            state.recentBackendFrameDurations = [];
        },
    },
});

export const {
    backendFramerateUpdated,
    frontendFramerateUpdated,
    clearFramerateHistory
} = framerateSlice.actions;
