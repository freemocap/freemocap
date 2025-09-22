// store/slices/server/simplified-server-thunks.ts
import { createAsyncThunk } from '@reduxjs/toolkit';
import type {RootState} from '@/store/types';
import {connectionOrchestrator} from "@/services/connection/connection-orchestrator.ts";

/**
 * Connect to server (managed or external)
 */
export const connectToServer = createAsyncThunk<
    { serverUrl: string;},
    {
        host?: string;
        port?: number;
        executablePath?: string | null;
    },
    { state: RootState }
>(
    'server/connect',
    async (args) => {
        const result = await connectionOrchestrator.connect({
            host: args.host,
            port: args.port,
            autoConnectWebSocket: true
        });

        if (!result.success) {
            throw new Error(result.error || 'Connection failed');
        }

        return {
            serverUrl: result.serverUrl!,
        };
    }
);

/**
 * Disconnect from server
 */
export const disconnectFromServer = createAsyncThunk<void>(
    'server/disconnect',
    async () => {
        await connectionOrchestrator.disconnect();
    }
);

/**
 * Check server health
 */
export const checkServerHealth = createAsyncThunk<
    boolean,
    void,
    { state: RootState }
>(
    'server/checkHealth',
    async (_, { getState }) => {
        const state = getState();
        const serverUrl = state.server.connection.serverUrl;

        if (!serverUrl) {
            return false;
        }

        return await connectionOrchestrator.checkHealth(serverUrl);
    }
);

/**
 * Refresh executable candidates
 */

/**
 * Auto-connect based on configuration
 */
export const autoConnect = createAsyncThunk<
    void,
    void,
    { state: RootState }
>(
    'server/autoConnect',
    async (_, { getState, dispatch }) => {
        const state = getState();
        const {  autoConnect } = state.server.config;

        // Already connected?
        if (connectionOrchestrator.isConnected()) {
            return;
        }

        // Try external connection first
        if (autoConnect) {
            try {
                await dispatch(connectToServer({})).unwrap();
                return;
            } catch {
                // Continue to auto-spawn if configured
            }
        }

    }
);
