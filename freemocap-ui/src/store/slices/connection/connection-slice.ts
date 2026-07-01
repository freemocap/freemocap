import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { AppStateMessage, ConnectionState } from './connection-types';

const initialState: ConnectionState = {
    isConnected: false,
    serverPid: null,
    cameraGroups: [],
    realtimePipelines: [],
};

export const connectionSlice = createSlice({
    name: 'connection',
    initialState,
    reducers: {
        // WebSocket open/closed — the single source of truth for "connected".
        wsConnectionChanged: (state, action: PayloadAction<boolean>) => {
            state.isConnected = action.payload;
        },
        // Authoritative server-state snapshot, pushed on connect and on change.
        // The cameras and realtime slices also listen for this to reconcile.
        serverStateReceived: (state, action: PayloadAction<AppStateMessage>) => {
            state.serverPid = action.payload.server_pid;
            state.cameraGroups = Object.values(action.payload.state.camera_groups);
            state.realtimePipelines = action.payload.state.realtime_pipelines ?? [];
        },
        // WebSocket dropped — clear server-derived state so nothing goes stale.
        serverDisconnected: (state) => {
            state.isConnected = false;
            state.serverPid = null;
            state.cameraGroups = [];
            state.realtimePipelines = [];
        },
    },
});

export const { wsConnectionChanged, serverStateReceived, serverDisconnected } = connectionSlice.actions;
