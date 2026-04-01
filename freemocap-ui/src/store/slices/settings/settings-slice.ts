import {createSlice, PayloadAction} from "@reduxjs/toolkit";
import {FreeMoCapSettings, SettingsStateMessage} from "./settings-types";

export interface ServerSettingsState {
    settings: FreeMoCapSettings | null;
    version: number;
    lastUpdated: string | null;
    isInitialized: boolean;
}

const initialState: ServerSettingsState = {
    settings: null,
    version: -1,
    lastUpdated: null,
    isInitialized: false,
};

export const settingsSlice = createSlice({
    name: "serverSettings",
    initialState,
    reducers: {
        /**
         * Replace the entire settings blob from a backend settings/state message.
         * Only applies if the incoming version is newer than what we have.
         */
        serverSettingsUpdated: (state, action: PayloadAction<SettingsStateMessage>) => {
            const {settings, version} = action.payload;
            if (version <= state.version) {
                return; // Stale message — ignore
            }
            state.settings = settings;
            state.version = version;
            state.lastUpdated = new Date().toISOString();
            state.isInitialized = true;
        },

        /**
         * Reset to initial state (e.g., on WebSocket disconnect).
         */
        serverSettingsCleared: (state) => {
            state.settings = null;
            state.version = -1;
            state.lastUpdated = null;
            state.isInitialized = false;
        },
    },
});

export const {
    serverSettingsUpdated,
    serverSettingsCleared,
} = settingsSlice.actions;
