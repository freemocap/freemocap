// store/slices/server/server-selectors.ts
import { createSelector } from '@reduxjs/toolkit';
import type {RootState} from "../../types.ts";

// Base selectors
export const selectServerState = (state: RootState) => state.server;
export const selectServerConfig = (state: RootState) => state.server.config;
export const selectServerConnection = (state: RootState) => state.server.connection;
export const selectWebSocketState = (state: RootState) => state.server.websocket;
export const selectExecutablesState = (state: RootState) => state.server.executables;

// Config selectors
export const selectServerHost = (state: RootState) => state.server.config.host;
export const selectServerPort = (state: RootState) => state.server.config.port;
export const selectAutoConnect = (state: RootState) => state.server.config.autoConnect;
export const selectAutoSpawn = (state: RootState) => state.server.config.autoSpawn;
export const selectPreferredExecutablePath = (state: RootState) =>
    state.server.config.preferredExecutablePath;

// Connection selectors
export const selectConnectionMode = (state: RootState) => state.server.connection.mode;
export const selectConnectionStatus = (state: RootState) => state.server.connection.status;
export const selectManagedProcess = (state: RootState) => state.server.connection.managedProcess;
export const selectServerUrl = (state: RootState) => state.server.connection.serverUrl;
export const selectConnectionError = (state: RootState) => state.server.connection.error;
export const selectLastHealthCheck = (state: RootState) => state.server.connection.lastHealthCheck;

// WebSocket selectors
export const selectWebSocketStatus = (state: RootState) => state.server.websocket.status;
export const selectWebSocketError = (state: RootState) => state.server.websocket.error;
export const selectWebSocketReconnectAttempts = (state: RootState) =>
    state.server.websocket.reconnectAttempts;

// Executable selectors
export const selectExecutableCandidates = (state: RootState) => state.server.executables.candidates;
export const selectIsRefreshingExecutables = (state: RootState) =>
    state.server.executables.isRefreshing;

// Computed selectors

/**
 * Is the server alive (connected)?
 * This is what the websocket service checks for auto-connect
 */
export const selectIsServerAlive = createSelector(
    [selectConnectionStatus],
    (status) => status === 'connected'
);

/**
 * Is the server connection active?
 */
export const selectIsServerConnected = createSelector(
    [selectConnectionStatus],
    (status) => status === 'connected'
);

/**
 * Is the server in a transitional state?
 */
export const selectIsServerTransitioning = createSelector(
    [selectConnectionStatus],
    (status) => status === 'connecting' || status === 'disconnecting'
);

/**
 * Do we have a managed server process?
 */
export const selectHasManagedServer = createSelector(
    [selectConnectionMode, selectManagedProcess],
    (mode, process) => mode === 'managed' && process !== null
);

/**
 * Are we connected to an external server?
 */
export const selectIsExternalConnection = createSelector(
    [selectConnectionMode],
    (mode) => mode === 'external'
);

/**
 * Is the WebSocket connected?
 */
export const selectIsWebSocketConnected = createSelector(
    [selectWebSocketStatus],
    (status) => status === 'connected'
);

/**
 * Is the WebSocket in a transitional state?
 */
export const selectIsWebSocketTransitioning = createSelector(
    [selectWebSocketStatus],
    (status) => status === 'connecting' || status === 'reconnecting'
);

/**
 * Can we connect to the server? (not already connected or transitioning)
 */
export const selectCanConnect = createSelector(
    [selectConnectionStatus],
    (status) => status === 'disconnected' || status === 'error'
);

/**
 * Can we disconnect from the server?
 */
export const selectCanDisconnect = createSelector(
    [selectConnectionStatus],
    (status) => status === 'connected' || status === 'error'
);

/**
 * Get the full server HTTP URL
 */
export const selectHttpUrl = createSelector(
    [selectServerUrl, selectServerHost, selectServerPort],
    (serverUrl, host, port) => serverUrl || `http://${host}:${port}`
);

/**
 * Get the WebSocket URL
 */
export const selectWebSocketUrl = createSelector(
    [selectServerUrl, selectServerHost, selectServerPort],
    (serverUrl, host, port) => {
        const baseUrl = serverUrl || `http://${host}:${port}`;
        // Convert http to ws
        const wsUrl = baseUrl.replace('http://', 'ws://').replace('https://', 'wss://');
        return `${wsUrl}/skellycam/websocket/connect`;
    }
);

/**
 * Get all server endpoints
 */
export const selectServerEndpoints = createSelector(
    [selectHttpUrl],
    (baseUrl) => ({
        // Server management
        health: `${baseUrl}/health`,
        shutdown: `${baseUrl}/shutdown`,

        // Camera endpoints
        detectCameras: `${baseUrl}/skellycam/camera/detect`,
        createGroup: `${baseUrl}/skellycam/camera/group/apply`,
        closeAll: `${baseUrl}/skellycam/camera/group/close/all`,
        updateConfigs: `${baseUrl}/skellycam/camera/update`,
        pauseUnpauseCameras: `${baseUrl}/skellycam/camera/group/all/pause_unpause`,

        // Recording endpoints
        startRecording: `${baseUrl}/skellycam/camera/group/all/record/start`,
        stopRecording: `${baseUrl}/skellycam/camera/group/all/record/stop`,

        // WebSocket
        websocket: baseUrl.replace('http://', 'ws://').replace('https://', 'wss://') +
            '/skellycam/websocket/connect',
    })
);

/**
 * Get valid executable candidates
 */
export const selectValidExecutables = createSelector(
    [selectExecutableCandidates],
    (candidates) => candidates.filter((c: { isValid: boolean; }) => c.isValid)
);

/**
 * Get server connection summary for UI
 */
export const selectServerSummary = createSelector(
    [
        selectConnectionMode,
        selectConnectionStatus,
        selectHasManagedServer,
        selectServerUrl,
        selectWebSocketStatus
    ],
    (mode, status, hasManaged, url, wsStatus) => ({
        mode,
        status,
        hasManaged,
        url,
        wsStatus,
        description: getConnectionDescription(mode, status)
    })
);

// Helper function for connection description
function getConnectionDescription(
    mode: string,
    status: string
): string {
    if (status === 'disconnected') {
        return 'Not connected';
    }

    if (status === 'connecting') {
        return mode === 'managed' ? 'Starting server...' : 'Connecting...';
    }

    if (status === 'disconnecting') {
        return 'Disconnecting...';
    }

    if (status === 'error') {
        return 'Connection error';
    }

    if (status === 'connected') {
        if (mode === 'managed') {
            return 'Connected (managed)';
        }
        if (mode === 'external') {
            return 'Connected (external)';
        }
    }

    return 'Unknown';
}
