// store/slices/server/server-slice.ts
import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type {
    ServerConfig,
    ServerState,
    ServerStatus,
    WebSocketStatus,
    ServerConnectionMode,
} from './server-types';
import {
    checkServerHealth,
    connectToServer,
    disconnectFromServer,
    refreshExecutableCandidates,
} from './server-thunks';

// Helper to load config from localStorage
const loadConfigFromStorage = (): ServerConfig => ({
    host: localStorage.getItem('server-host') || 'localhost',
    port: parseInt(localStorage.getItem('server-port') || '8006'),
    autoConnect: localStorage.getItem('server-auto-connect') === 'true',
    autoSpawn: localStorage.getItem('server-auto-spawn') === 'true',
    preferredExecutablePath: localStorage.getItem('server-executable-path') || null,
});

// Helper to save config to localStorage
const saveConfigToStorage = (config: Partial<ServerConfig>): void => {
    if (config.host !== undefined) {
        localStorage.setItem('server-host', config.host);
    }
    if (config.port !== undefined) {
        localStorage.setItem('server-port', config.port.toString());
    }
    if (config.autoConnect !== undefined) {
        localStorage.setItem('server-auto-connect', config.autoConnect.toString());
    }
    if (config.autoSpawn !== undefined) {
        localStorage.setItem('server-auto-spawn', config.autoSpawn.toString());
    }
    if (config.preferredExecutablePath !== undefined) {
        localStorage.setItem('server-executable-path', config.preferredExecutablePath || '');
    }
};

const initialState: ServerState = {
    // Configuration
    config: loadConfigFromStorage(),

    // Connection info
    connection: {
        mode: 'none',
        status: 'disconnected',
        managedProcess: null,
        serverUrl: null,
        error: null,
        lastHealthCheck: null,
        retryCount: 0,
    },

    // WebSocket state
    websocket: {
        status: 'disconnected',
        error: null,
        reconnectAttempts: 0,
        lastConnectedAt: null,
        lastDisconnectedAt: null,
    },

    // Executable management (Electron only)
    executables: {
        candidates: [],
        lastRefresh: null,
        isRefreshing: false,
    }
};

export const connectionSlice = createSlice({
    name: 'server',
    initialState,
    reducers: {
        // Configuration
        updateServerConfig: (state, action: PayloadAction<Partial<ServerConfig>>) => {
            state.config = { ...state.config, ...action.payload };
            saveConfigToStorage(action.payload);
        },

        // Connection management
        connectionModeChanged: (state, action: PayloadAction<ServerConnectionMode>) => {
            state.connection.mode = action.payload;
        },

        connectionStatusChanged: (state, action: PayloadAction<ServerStatus>) => {
            state.connection.status = action.payload;
        },

        connectionErrorSet: (state, action: PayloadAction<string | null>) => {
            state.connection.error = action.payload;
        },

        managedProcessUpdated: (state, action: PayloadAction<{
            pid: number | null;
            executablePath: string | null;
        } | null>) => {
            state.connection.managedProcess = action.payload;
        },

        serverUrlUpdated: (state, action: PayloadAction<string | null>) => {
            state.connection.serverUrl = action.payload;
        },

        serverHealthCheckCompleted: (state, action: PayloadAction<boolean>) => {
            state.connection.lastHealthCheck = new Date().toISOString();
            if (action.payload && state.connection.status !== 'connected') {
                state.connection.status = 'connected';
            } else if (!action.payload && state.connection.status === 'connected') {
                state.connection.status = 'error';
                state.connection.error = 'Server health check failed';
            }
        },

        // WebSocket management
        websocketStatusChanged: (state, action: PayloadAction<WebSocketStatus>) => {
            state.websocket.status = action.payload;

            if (action.payload === 'connected') {
                state.websocket.error = null;
                state.websocket.reconnectAttempts = 0;
                state.websocket.lastConnectedAt = new Date().toISOString();
            } else if (action.payload === 'disconnected') {
                state.websocket.lastDisconnectedAt = new Date().toISOString();
            }
        },

        websocketConnected: (state) => {
            state.websocket.status = 'connected';
            state.websocket.error = null;
            state.websocket.reconnectAttempts = 0;
            state.websocket.lastConnectedAt = new Date().toISOString();
        },

        websocketDisconnected: (state) => {
            state.websocket.status = 'disconnected';
            state.websocket.lastDisconnectedAt = new Date().toISOString();
        },

        websocketConnecting: (state) => {
            state.websocket.status = 'connecting';
        },

        websocketReconnecting: (state, action: PayloadAction<number>) => {
            state.websocket.status = 'reconnecting';
            state.websocket.reconnectAttempts = action.payload;
        },

        websocketError: (state, action: PayloadAction<string>) => {
            state.websocket.status = 'error';
            state.websocket.error = action.payload;
        },

        // Executable management
        executablesUpdated: (state, action: PayloadAction<[]>) => {
            state.executables.candidates = action.payload;
            state.executables.lastRefresh = new Date().toISOString();
            state.executables.isRefreshing = false;
        },

        executablesRefreshing: (state) => {
            state.executables.isRefreshing = true;
        },
    },

    extraReducers: (builder) => {
        builder
            // Connect to server
            .addCase(connectToServer.pending, (state, action) => {
                state.connection.mode = action.meta.arg.mode;
                state.connection.status = 'connecting';
                state.connection.error = null;
                state.connection.retryCount = 0;
            })
            .addCase(connectToServer.fulfilled, () => {
                // The orchestrator handles most state updates via dispatched actions
                // This is just for any final cleanup
            })
            .addCase(connectToServer.rejected, (state, action) => {
                state.connection.status = 'error';
                state.connection.error = action.error.message || 'Failed to connect';
                state.connection.mode = 'none';
            })

            // Disconnect from server
            .addCase(disconnectFromServer.pending, (state) => {
                state.connection.status = 'disconnecting';
            })
            .addCase(disconnectFromServer.fulfilled, (state) => {
                state.connection.mode = 'none';
                state.connection.status = 'disconnected';
                state.connection.managedProcess = null;
                state.connection.serverUrl = null;
                state.websocket.status = 'disconnected';
            })
            .addCase(disconnectFromServer.rejected, (state, action) => {
                state.connection.error = action.error.message || 'Failed to disconnect';
            })

            // Health checks
            .addCase(checkServerHealth.fulfilled, (state, action) => {
                state.connection.lastHealthCheck = new Date().toISOString();
                if (action.payload) {
                    if (state.connection.status === 'connecting') {
                        state.connection.status = 'connected';
                    }
                } else if (state.connection.status === 'connected') {
                    state.connection.status = 'error';
                    state.connection.error = 'Server health check failed';
                }
            })

            // Refresh executables
            .addCase(refreshExecutableCandidates.pending, (state) => {
                state.executables.isRefreshing = true;
            })
            .addCase(refreshExecutableCandidates.fulfilled, (state, action) => {
                state.executables.candidates = action.payload;
                state.executables.lastRefresh = new Date().toISOString();
                state.executables.isRefreshing = false;
            })
            .addCase(refreshExecutableCandidates.rejected, (state) => {
                state.executables.isRefreshing = false;
            });
    },
});

export const {
    updateServerConfig,
    connectionModeChanged,
    connectionStatusChanged,
    connectionErrorSet,
    managedProcessUpdated,
    serverUrlUpdated,
    serverHealthCheckCompleted,
    websocketStatusChanged,
    websocketConnected,
    websocketDisconnected,
    websocketConnecting,
    websocketReconnecting,
    websocketError,
    executablesUpdated,
    executablesRefreshing,
} = connectionSlice.actions;
