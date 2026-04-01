// framerate-slice.ts
import {createSlice, PayloadAction} from '@reduxjs/toolkit';
import {DetailedFramerate} from './framerate-types';

// Export DetailedFramerate as CurrentFramerate for component compatibility
export type CurrentFramerate = DetailedFramerate;

interface FramerateState {
    currentBackendFramerate: DetailedFramerate | null;
    currentFrontendFramerate: DetailedFramerate | null;
    // Arrays for historical data to calculate averages and render charts
    recentFrontendFrameDurations: number[];
    recentBackendFrameDurations: number[];
}

const initialState: FramerateState = {
    currentBackendFramerate: null,
    currentFrontendFramerate: null,
    recentFrontendFrameDurations: [],
    recentBackendFrameDurations: [],
};

const MAX_DURATION_HISTORY = 100; // Keep last 100 frame durations

export const framerateSlice = createSlice({
    name: 'framerate',
    initialState,
    reducers: {
        backendFramerateUpdated: (state, action: PayloadAction<DetailedFramerate>) => {
            state.currentBackendFramerate = action.payload;
            // Add mean frame duration to history
            if (action.payload.mean_frame_duration_ms > 0) {
                state.recentBackendFrameDurations = [
                    ...state.recentBackendFrameDurations.slice(-(MAX_DURATION_HISTORY - 1)),
                    action.payload.mean_frame_duration_ms
                ];
            }
        },
        frontendFramerateUpdated: (state, action: PayloadAction<DetailedFramerate>) => {
            state.currentFrontendFramerate = action.payload;
            // Add mean frame duration to history
            if (action.payload.mean_frame_duration_ms > 0) {
                state.recentFrontendFrameDurations = [
                    ...state.recentFrontendFrameDurations.slice(-(MAX_DURATION_HISTORY - 1)),
                    action.payload.mean_frame_duration_ms
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
