// framerate-selectors.ts
import {createSelector} from '@reduxjs/toolkit';
import {RootState} from '../../types';
import {DetailedFramerate} from './framerate-types';

// Basic selectors for current framerates
export const selectCurrentFrontendFramerate = (state: RootState): DetailedFramerate | null =>
    state.framerate.currentFrontendFramerate;

export const selectCurrentBackendFramerate = (state: RootState): DetailedFramerate | null =>
    state.framerate.currentBackendFramerate;

// Quick FPS value selectors
export const selectFrontendFps = (state: RootState): number =>
    state.framerate.currentFrontendFramerate?.mean_frames_per_second ?? 0;

export const selectBackendFps = (state: RootState): number =>
    state.framerate.currentBackendFramerate?.mean_frames_per_second ?? 0;

// Historical data selectors
export const selectRecentFrontendFrameDurations = (state: RootState): number[] =>
    state.framerate.recentFrontendFrameDurations;

export const selectRecentBackendFrameDurations = (state: RootState): number[] =>
    state.framerate.recentBackendFrameDurations;

// Calculated average framerates from historical data
export const selectAverageFramerates = createSelector(
    [selectRecentFrontendFrameDurations, selectRecentBackendFrameDurations],
    (frontendDurations, backendDurations) => {
        const calcAverage = (durations: number[]): number => {
            if (durations.length === 0) return 0;
            const sum = durations.reduce((a, b) => a + b, 0);
            return 1000 / (sum / durations.length); // Convert ms to FPS
        };

        return {
            frontend: calcAverage(frontendDurations),
            backend: calcAverage(backendDurations),
        };
    }
);

// Statistics selectors
export const selectFramerateStatistics = createSelector(
    [selectCurrentFrontendFramerate, selectCurrentBackendFramerate],
    (frontend, backend) => ({
        frontend: {
            mean: frontend?.mean_frames_per_second ?? 0,
            std: frontend?.frame_duration_stddev ?? 0,
            current: frontend?.mean_frames_per_second ?? 0,
        },
        backend: {
            mean: backend?.mean_frames_per_second ?? 0,
            std: backend?.frame_duration_stddev ?? 0,
            current: backend?.mean_frames_per_second ?? 0,
        },
    })
);

// Combined selector for UI components that need all framerate info
export const selectFramerateInfo = createSelector(
    [
        selectCurrentFrontendFramerate,
        selectCurrentBackendFramerate,
        selectAverageFramerates,
    ],
    (frontend, backend, averages) => ({
        frontend: {
            current: frontend?.mean_frames_per_second ?? 0,
            mean: frontend?.mean_frames_per_second ?? 0,
            std: frontend?.frame_duration_stddev ?? 0,
            average: averages.frontend,
        },
        backend: {
            current: backend?.mean_frames_per_second ?? 0,
            mean: backend?.mean_frames_per_second ?? 0,
            std: backend?.frame_duration_stddev ?? 0,
            average: averages.backend,
        },
    })
);

// Selector for all framerate data needed by the viewer components
export const selectFramerateViewerData = createSelector(
    [
        selectCurrentFrontendFramerate,
        selectCurrentBackendFramerate,
        selectRecentFrontendFrameDurations,
        selectRecentBackendFrameDurations,
    ],
    (currentFrontendFramerate, currentBackendFramerate, recentFrontendFrameDurations, recentBackendFrameDurations) => ({
        currentFrontendFramerate,
        currentBackendFramerate,
        recentFrontendFrameDurations,
        recentBackendFrameDurations,
    })
);
