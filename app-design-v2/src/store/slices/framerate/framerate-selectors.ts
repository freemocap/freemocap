// framerate-selectors.ts
import { createSelector } from '@reduxjs/toolkit';
import type {RootState} from '../../types';

// Basic selectors for current framerates
export const selectFrontendFramerate = (state: RootState) =>
    state.framerate.frontend?.current ?? 0;

export const selectBackendFramerate = (state: RootState) =>
    state.framerate.backend?.current ?? 0;

// Full framerate data selectors
export const selectFrontendFramerateData = (state: RootState) =>
    state.framerate.frontend;

export const selectBackendFramerateData = (state: RootState) =>
    state.framerate.backend;

// Historical data selectors
export const selectRecentFrontendFrameDurations = (state: RootState) =>
    state.framerate.recentFrontendFrameDurations;

export const selectRecentBackendFrameDurations = (state: RootState) =>
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
    [selectFrontendFramerateData, selectBackendFramerateData],
    (frontend, backend) => ({
        frontend: {
            mean: frontend?.mean ?? 0,
            std: frontend?.std ?? 0,
            current: frontend?.current ?? 0,
        },
        backend: {
            mean: backend?.mean ?? 0,
            std: backend?.std ?? 0,
            current: backend?.current ?? 0,
        },
    })
);

// Combined selector for UI components that need all framerate info
export const selectFramerateInfo = createSelector(
    [
        selectFrontendFramerateData,
        selectBackendFramerateData,
        selectAverageFramerates,
    ],
    (frontend, backend, averages) => ({
        frontend: {
            current: frontend?.current ?? 0,
            mean: frontend?.mean ?? 0,
            std: frontend?.std ?? 0,
            average: averages.frontend,
        },
        backend: {
            current: backend?.current ?? 0,
            mean: backend?.mean ?? 0,
            std: backend?.std ?? 0,
            average: averages.backend,
        },
    })
);
