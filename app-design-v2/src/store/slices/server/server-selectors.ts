// store/slices/server/server-selectors.ts
import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from "../../types.ts";
import type { ServerStatus } from './server-types';

// Base selectors
export const selectServerState = (state: RootState) => state.server;
export const selectServerConfig = (state: RootState) => state.server.config;
export const selectServerConnection = (state: RootState) => state.server.connection;

// Config selectors
export const selectServerHost = (state: RootState) => state.server.config.host;
export const selectServerPort = (state: RootState) => state.server.config.port;

// Connection selectors
export const selectConnectionStatus = (state: RootState) => state.server.connection.status;
export const selectServerUrl = (state: RootState) => state.server.connection.serverUrl;
export const selectConnectionError = (state: RootState) => state.server.connection.error;
export const selectLastHealthCheck = (state: RootState) => state.server.connection.lastHealthCheck;
export const selectRetryCount = (state: RootState) => state.server.connection.retryCount;

/**
 * Is the server healthy (connected)?
 * This is what the websocket service checks for auto-connect
 */
export const selectIsServerAlive = createSelector(
    [selectConnectionStatus],
    (status) => status === 'healthy'
);

/**
 * Is the server healthy and available?
 */
export const selectIsServerHealthy = createSelector(
    [selectConnectionStatus],
    (status) => status === 'healthy'
);

/**
 * Is the server in a transitional state?
 */
export const selectIsServerTransitioning = createSelector(
    [selectConnectionStatus],
    (status) => status === 'closing'
);

/**
 * Can we connect to the server? (not already healthy or closing)
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
    (status) => status === 'healthy'
);

/**
 * Can we shutdown the server?
 */
export const selectCanShutdown = createSelector(
    [selectConnectionStatus],
    (status) => status === 'healthy'
);

/**
 * Is the server in an error state?
 */
export const selectIsServerError = createSelector(
    [selectConnectionStatus],
    (status) => status === 'error'
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
 * Get server connection summary for UI
 */
export const selectServerSummary = createSelector(
    [
        selectConnectionStatus,
        selectServerUrl,
    ],
    (status, url) => ({
        status,
        url,
        description: getConnectionDescription(status)
    })
);

// Helper function for connection description
function getConnectionDescription(
    status: ServerStatus
): string {
    switch (status) {
        case 'disconnected':
            return 'Not connected';
        case 'healthy':
            return 'Connected';
        case 'closing':
            return 'Shutting down...';
        case 'error':
            return 'Connection error';
        default:
            return 'Unknown';
    }
}
