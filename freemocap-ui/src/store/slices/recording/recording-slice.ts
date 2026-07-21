import {createSlice, PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '@/store/types';
import {ComputedRecordingPath, PendingOperation, RecordingConfig, RecordingInfo} from './recording-types';
import {startRecording, stopRecording} from './recording-thunks';
import {loadFromStorage} from '@/store/persistence';
import {getTimestampString} from './getTimestampString';

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

// Empty until hydrated from the base data folder at startup (see useHydrateDataFolder).
const DEFAULT_RECORDING_DIRECTORY = '';

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

const initialState: RecordingInfo = {
    isRecording: false,
    recordingDirectory: _persistedDirectory ?? DEFAULT_RECORDING_DIRECTORY,
    recordingName: null,
    startedAt: null,
    duration: 0,
    completionData: null,
    config: _persistedConfig ?? { ...DEFAULT_RECORDING_CONFIG },
    computed: {
        recordingName: '',
        subfolderName: '',
        fullRecordingPath: _persistedDirectory ?? DEFAULT_RECORDING_DIRECTORY,
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

