// store/slices/server/server-selectors.ts
import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from "../../types.ts";

// Base selectors
export const selectServerConfig = (state: RootState) => state.server.config;

// Config selectors
export const selectServerHost = (state: RootState) => state.server.config.host;
export const selectServerPort = (state: RootState) => state.server.config.port;

// Connection selectors
export const selectServerUrl = (state: RootState) => state.server.connection.serverUrl;


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

