// store/slices/server/server-slice.ts
import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type {
    ServerConfig,
    ServerState,
    ServerStatus,
} from './server-types';
import {
    checkServerHealth,
    shutdownServer,
} from './server-thunks';

// Helper to load config from localStorage
const loadConfigFromStorage = (): ServerConfig => ({
    host: localStorage.getItem('server-host') || 'localhost',
    port: parseInt(localStorage.getItem('server-port') || '8006'),
});

// Helper to save config to localStorage
const saveConfigToStorage = (config: Partial<ServerConfig>): void => {
    if (config.host !== undefined) {
        localStorage.setItem('server-host', config.host);
    }
    if (config.port !== undefined) {
        localStorage.setItem('server-port', config.port.toString());
    }
};

const initialState: ServerState = {
    // Configuration
    config: loadConfigFromStorage(),

    // Connection info
    connection: {
        status: 'disconnected',
        serverUrl: null,
        error: null,
        lastHealthCheck: null,
        retryCount: 0,
    },
};

export const serverSlice = createSlice({
    name: 'server',
    initialState,
    reducers: {
        // Configuration
        updateServerConfig: (state, action: PayloadAction<Partial<ServerConfig>>) => {
            state.config = { ...state.config, ...action.payload };
            saveConfigToStorage(action.payload);
        },

        connectionStatusChanged: (state, action: PayloadAction<ServerStatus>) => {
            state.connection.status = action.payload;
        },

        connectionErrorSet: (state, action: PayloadAction<string | null>) => {
            state.connection.error = action.payload;
        },

        serverUrlUpdated: (state, action: PayloadAction<string | null>) => {
            state.connection.serverUrl = action.payload;
        },

        serverHealthCheckCompleted: (state, action: PayloadAction<boolean>) => {
            state.connection.lastHealthCheck = new Date().toISOString();
            if (action.payload && state.connection.status !== 'healthy') {
                state.connection.status = 'healthy';
                state.connection.error = null;
            } else if (!action.payload && state.connection.status === 'healthy') {
                state.connection.status = 'error';
                state.connection.error = 'Server health check failed';
            }
        },

        retryCountIncremented: (state) => {
            state.connection.retryCount += 1;
        },

        retryCountReset: (state) => {
            state.connection.retryCount = 0;
        },
    },

    extraReducers: (builder) => {
        builder
            // Health checks
            .addCase(checkServerHealth.fulfilled, (state, action) => {
                state.connection.lastHealthCheck = new Date().toISOString();
                if (action.payload) {
                    state.connection.status = 'healthy';
                    state.connection.error = null;
                    state.connection.retryCount = 0;
                } else {
                    // Only change to error if we were previously healthy
                    if (state.connection.status === 'healthy') {
                        state.connection.status = 'error';
                        state.connection.error = 'Server health check failed';
                    }
                    state.connection.retryCount += 1;
                }
            })
            .addCase(checkServerHealth.rejected, (state) => {
                state.connection.lastHealthCheck = new Date().toISOString();
                if (state.connection.status === 'healthy') {
                    state.connection.status = 'error';
                    state.connection.error = 'Health check failed';
                }
                state.connection.retryCount += 1;
            })

            // Shutdown server
            .addCase(shutdownServer.pending, (state) => {
                state.connection.status = 'closing';
            })
            .addCase(shutdownServer.fulfilled, (state) => {
                state.connection.status = 'disconnected';
                state.connection.serverUrl = null;
                state.connection.error = null;
            })
            .addCase(shutdownServer.rejected, (state, action) => {
                state.connection.status = 'error';
                state.connection.error = action.error.message || 'Failed to shutdown server';
            });
    },
});

export const {
    updateServerConfig,
    connectionStatusChanged,
    connectionErrorSet,
    serverUrlUpdated,
    serverHealthCheckCompleted,
    retryCountIncremented,
    retryCountReset,
} = serverSlice.actions;
