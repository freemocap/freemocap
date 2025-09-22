// store/slices/server/server-thunks.ts
import { createAsyncThunk } from '@reduxjs/toolkit';
import type { RootState } from '../../types';
import { selectServerEndpoints } from './server-selectors';

/**
 * Check server health status
 */
export const checkServerHealth = createAsyncThunk<
    boolean,
    void,
    { state: RootState }
>(
    'server/checkHealth',
    async (_, { getState }) => {
        const state = getState();
        const endpoints = selectServerEndpoints(state);

        try {
            const response = await fetch(endpoints.health, {
                method: 'GET',
                signal: AbortSignal.timeout(5000), // 5 second timeout
            });

            return response.ok;
        } catch (error) {
            console.error('Health check failed:', error);
            return false;
        }
    }
);

/**
 * Shutdown the server
 */
export const shutdownServer = createAsyncThunk<
    void,
    void,
    { state: RootState }
>(
    'server/shutdown',
    async (_, { getState }) => {
        const state = getState();
        const endpoints = selectServerEndpoints(state);

        try {
            const response = await fetch(endpoints.shutdown, {
                method: 'POST',
                signal: AbortSignal.timeout(5000),
            });

            if (!response.ok) {
                throw new Error(`Shutdown failed with status: ${response.status}`);
            }
        } catch (error) {
            throw new Error(
                error instanceof Error
                    ? error.message
                    : 'Failed to shutdown server'
            );
        }
    }
);
