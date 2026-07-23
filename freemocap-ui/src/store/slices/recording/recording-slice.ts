import {createSlice, PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '@/store/types';
import {ComputedRecordingPath, PendingOperation, RecordingConfig, RecordingInfo} from './recording-types';
import {startRecording, stopRecording} from './recording-thunks';
import {loadFromStorage} from '@/store/persistence';
import {getTimestampString} from './getTimestampString';
import {recordingsDirFromBaseFolder} from '@/utils/dataFolder';

const computeRecordingPath = (
    recordingDirectory: string,
    config: RecordingConfig
): ComputedRecordingPath => {
    const parts: string[] = [];

    if (config.useTimestamp) {
        parts.push(getTimestampString());
    } else {
        parts.push(config.baseName);
    }

    if (config.useIncrement) {
        parts.push(String(config.currentIncrement).padStart(3, '0'));
    }

    if (config.recordingTag) {
        parts.push(config.recordingTag);
    }

    const recordingName = parts.join("_");

    const subfolderName = config.createSubfolder
        ? config.customSubfolderName || getTimestampString()
        : "";

    const fullRecordingPath = config.createSubfolder
        ? `${recordingDirectory}/${subfolderName}`
        : recordingDirectory;

    return {
        recordingName,
        subfolderName,
        fullRecordingPath,
    };
};

// The recording directory must NEVER be empty — it is always either the user's persisted
// override or a real path derived from the base data folder. The base data folder itself is
// resolved by Electron main (override-or-`~/freemocap_data`, see electron/main/base-folder.ts)
// and handed to the renderer *synchronously* at preload time (electron/preload/index.ts), so it
// is available before this module — and therefore this initial state — ever runs. There is no
// async hydration step and no window where this can be blank.
//
// The literal fallback below only activates when there is no Electron main process to ask at all
// (e.g. `npm run dev`'s bare Vite server opened directly in a browser tab) — a dev-only scenario
// with no real filesystem to resolve `~` against client-side.
const FALLBACK_RECORDING_DIRECTORY = '~/freemocap_data/recordings';

function resolveDefaultRecordingDirectory(): string {
    const baseDataFolder = typeof window !== 'undefined' && window.electronAPI
        ? window.electronAPI.baseDataFolder
        : undefined;
    return baseDataFolder ? recordingsDirFromBaseFolder(baseDataFolder) : FALLBACK_RECORDING_DIRECTORY;
}

const DEFAULT_RECORDING_DIRECTORY = resolveDefaultRecordingDirectory();

const DEFAULT_RECORDING_CONFIG: RecordingConfig = {
    useDelayStart: false,
    delaySeconds: 3,
    useTimestamp: true,
    useIncrement: false,
    currentIncrement: 1,
    baseName: 'recording',
    recordingTag: '',
    createSubfolder: false,
    customSubfolderName: '',
    micDeviceIndex: -1,
    autoProcess: true,
};

const _persistedConfig = loadFromStorage<RecordingConfig | null>('recording.config', null);
const _persistedDirectory = loadFromStorage<string | null>('recording.directory', null);
// A blank/whitespace persisted value means "not actually set" (e.g. saved while this bug was
// live) — treat it the same as no persisted value at all, never carry '' forward.
const _initialRecordingDirectory = _persistedDirectory && _persistedDirectory.trim()
    ? _persistedDirectory
    : DEFAULT_RECORDING_DIRECTORY;

const initialState: RecordingInfo = {
    isRecording: false,
    recordingDirectory: _initialRecordingDirectory,
    recordingName: null,
    startedAt: null,
    duration: 0,
    completionData: null,
    config: _persistedConfig ?? { ...DEFAULT_RECORDING_CONFIG },
    computed: {
        recordingName: '',
        subfolderName: '',
        fullRecordingPath: _initialRecordingDirectory,
    },
    pendingOperation: null,
    countdown: null,
};

// Initialize computed values
initialState.computed = computeRecordingPath(
    initialState.recordingDirectory,
    initialState.config
);

export const recordingSlice = createSlice({
    name: 'recording',
    initialState,
    reducers: {
        recordingInfoUpdated: (state, action: PayloadAction<Partial<RecordingInfo>>) => {
            Object.assign(state, action.payload);
            state.computed = computeRecordingPath(state.recordingDirectory, state.config);
        },
        recordingDirectoryChanged: (state, action: PayloadAction<string>) => {
            state.recordingDirectory = action.payload;
            state.computed = computeRecordingPath(state.recordingDirectory, state.config);
        },
        recordingDurationUpdated: (state, action: PayloadAction<number>) => {
            state.duration = action.payload;
        },

        // Config updates
        configUpdated: (state, action: PayloadAction<Partial<RecordingConfig>>) => {
            Object.assign(state.config, action.payload);
            state.computed = computeRecordingPath(state.recordingDirectory, state.config);
        },
        useDelayStartToggled: (state, action: PayloadAction<boolean>) => {
            state.config.useDelayStart = action.payload;
            // No need to recompute path for delay settings
        },
        delaySecondsChanged: (state, action: PayloadAction<number>) => {
            state.config.delaySeconds = action.payload;
            // No need to recompute path for delay settings
        },
        useTimestampToggled: (state, action: PayloadAction<boolean>) => {
            state.config.useTimestamp = action.payload;
            state.computed = computeRecordingPath(state.recordingDirectory, state.config);
        },
        useIncrementToggled: (state, action: PayloadAction<boolean>) => {
            state.config.useIncrement = action.payload;
            state.computed = computeRecordingPath(state.recordingDirectory, state.config);
        },
        currentIncrementChanged: (state, action: PayloadAction<number>) => {
            state.config.currentIncrement = action.payload;
            state.computed = computeRecordingPath(state.recordingDirectory, state.config);
        },
        currentIncrementIncremented: (state) => {
            state.config.currentIncrement += 1;
            state.computed = computeRecordingPath(state.recordingDirectory, state.config);
        },
        baseNameChanged: (state, action: PayloadAction<string>) => {
            state.config.baseName = action.payload;
            state.computed = computeRecordingPath(state.recordingDirectory, state.config);
        },
        recordingTagChanged: (state, action: PayloadAction<string>) => {
            state.config.recordingTag = action.payload;
            state.computed = computeRecordingPath(state.recordingDirectory, state.config);
        },
        createSubfolderToggled: (state, action: PayloadAction<boolean>) => {
            state.config.createSubfolder = action.payload;
            state.computed = computeRecordingPath(state.recordingDirectory, state.config);
        },
        customSubfolderNameChanged: (state, action: PayloadAction<string>) => {
            state.config.customSubfolderName = action.payload;
            state.computed = computeRecordingPath(state.recordingDirectory, state.config);
        },
        // Force recomputation of path (useful for timestamp updates)
        pathRecomputed: (state) => {
            const next = computeRecordingPath(state.recordingDirectory, state.config);
            if (
                next.recordingName === state.computed.recordingName &&
                next.subfolderName === state.computed.subfolderName &&
                next.fullRecordingPath === state.computed.fullRecordingPath
            ) return;
            state.computed = next;
        },
        recordingCompletionDismissed: (state) => {
            state.completionData = null;
        },
        micDeviceIndexChanged: (state, action: PayloadAction<number>) => {
            state.config.micDeviceIndex = action.payload;
        },
        autoProcessToggled: (state, action: PayloadAction<boolean>) => {
            state.config.autoProcess = action.payload;
        },
        pendingOperationSet: (state, action: PayloadAction<PendingOperation | null>) => {
            state.pendingOperation = action.payload;
        },
        countdownSet: (state, action: PayloadAction<number | null>) => {
            state.countdown = action.payload;
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(startRecording.fulfilled, (state, action) => {
                state.isRecording = true;
                state.recordingName = action.meta.arg.recordingName;
                state.startedAt = new Date().toISOString();
                state.duration = 0;
                state.pendingOperation = null;
            })
            .addCase(stopRecording.fulfilled, (state, action) => {
                state.isRecording = false;
                state.recordingName = null;
                state.startedAt = null;
                state.duration = 0;
                state.completionData = action.payload;
                state.pendingOperation = null;
            });
    },
});

export const {
    recordingInfoUpdated,
    recordingDirectoryChanged,
    recordingDurationUpdated,
    configUpdated,
    useDelayStartToggled,
    delaySecondsChanged,
    useTimestampToggled,
    useIncrementToggled,
    currentIncrementChanged,
    currentIncrementIncremented,
    baseNameChanged,
    recordingTagChanged,
    createSubfolderToggled,
    customSubfolderNameChanged,
    pathRecomputed,
    recordingCompletionDismissed,
    micDeviceIndexChanged,
    autoProcessToggled,
    pendingOperationSet,
    countdownSet,
} = recordingSlice.actions;

/**
 * Shared selector: returns true when ANY recording mode is active
 * (regular recording, calibration recording, or mocap recording).
 * Use this for UI elements that should respond to any recording —
 * camera red outlines, disabling camera controls, etc.
 */
export const selectIsAnyRecording = (state: RootState): boolean =>
    state.recording.isRecording ||
    state.calibration.isRecording ||
    state.mocap.isRecording;

