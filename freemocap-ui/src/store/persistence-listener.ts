import {createListenerMiddleware} from '@reduxjs/toolkit';
import {RootState} from './types';
import {saveToStorage} from './persistence';

export const persistenceListenerMiddleware = createListenerMiddleware();

// How long to wait after the last change before writing to localStorage.
// Rapid sequential actions (e.g. dragging a slider) collapse into one write.
const DEBOUNCE_MS = 300;

// ─── activeRecording ──────────────────────────────────────────────────────────
// Only persist the 3 user-meaningful fields; 'origin' is transient.
persistenceListenerMiddleware.startListening({
    predicate: (_, curr, prev) => {
        const c = (curr as RootState).activeRecording;
        const p = (prev as RootState).activeRecording;
        return c.recordingName !== p.recordingName
            || c.baseDirectory !== p.baseDirectory
            || c.layoutPreset !== p.layoutPreset;
    },
    effect: async (_, api) => {
        api.cancelActiveListeners();
        await api.delay(DEBOUNCE_MS);
        const s = api.getState() as RootState;
        saveToStorage('activeRecording', {
            recordingName: s.activeRecording.recordingName,
            baseDirectory: s.activeRecording.baseDirectory,
            layoutPreset: s.activeRecording.layoutPreset,
        });
    },
});

// ─── recording.config ─────────────────────────────────────────────────────────
persistenceListenerMiddleware.startListening({
    predicate: (_, curr, prev) =>
        (curr as RootState).recording.config !== (prev as RootState).recording.config,
    effect: async (_, api) => {
        api.cancelActiveListeners();
        await api.delay(DEBOUNCE_MS);
        saveToStorage('recording.config', (api.getState() as RootState).recording.config);
    },
});

// ─── recording.directory ──────────────────────────────────────────────────────
persistenceListenerMiddleware.startListening({
    predicate: (_, curr, prev) =>
        (curr as RootState).recording.recordingDirectory !== (prev as RootState).recording.recordingDirectory,
    effect: async (_, api) => {
        api.cancelActiveListeners();
        await api.delay(DEBOUNCE_MS);
        saveToStorage('recording.directory', (api.getState() as RootState).recording.recordingDirectory);
    },
});

// ─── calibration.config ───────────────────────────────────────────────────────
persistenceListenerMiddleware.startListening({
    predicate: (_, curr, prev) =>
        (curr as RootState).calibration.config !== (prev as RootState).calibration.config,
    effect: async (_, api) => {
        api.cancelActiveListeners();
        await api.delay(DEBOUNCE_MS);
        saveToStorage('calibration.config', (api.getState() as RootState).calibration.config);
    },
});

// ─── mocap.config ─────────────────────────────────────────────────────────────
persistenceListenerMiddleware.startListening({
    predicate: (_, curr, prev) =>
        (curr as RootState).mocap.config !== (prev as RootState).mocap.config,
    effect: async (_, api) => {
        api.cancelActiveListeners();
        await api.delay(DEBOUNCE_MS);
        saveToStorage('mocap.config', (api.getState() as RootState).mocap.config);
    },
});

// ─── blender.settings ─────────────────────────────────────────────────────────
persistenceListenerMiddleware.startListening({
    predicate: (_, curr, prev) => {
        const c = (curr as RootState).blender;
        const p = (prev as RootState).blender;
        return c.blenderExePath !== p.blenderExePath
            || c.exportToBlenderEnabled !== p.exportToBlenderEnabled
            || c.autoOpenBlendFile !== p.autoOpenBlendFile;
    },
    effect: async (_, api) => {
        api.cancelActiveListeners();
        await api.delay(DEBOUNCE_MS);
        const s = api.getState() as RootState;
        saveToStorage('blender.settings', {
            blenderExePath: s.blender.blenderExePath,
            exportToBlenderEnabled: s.blender.exportToBlenderEnabled,
            autoOpenBlendFile: s.blender.autoOpenBlendFile,
        });
    },
});
