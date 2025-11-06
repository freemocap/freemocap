import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { RecordingInfo, RecordingConfig, ComputedRecordingPath } from './recording-types';
import { startRecording, stopRecording } from './recording-thunks';

const getTimestampString = (): string => {
    const now = new Date();

    const dateOptions: Intl.DateTimeFormatOptions = {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
        timeZoneName: "shortOffset",
    };

    const formatter = new Intl.DateTimeFormat("en-US", dateOptions);
    const parts = formatter.formatToParts(now);

    const partMap: Record<string, string> = {};
    parts.forEach((part) => {
        partMap[part.type] = part.value;
    });

    return `${partMap.year}-${partMap.month}-${partMap.day}_${partMap.hour}-${partMap.minute}-${partMap.second}_${partMap.timeZoneName.replace(":", "")}`;
};

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

const initialState: RecordingInfo = {
    isRecording: false,
    recordingDirectory: '~/freemocap_data/recordings',
    recordingName: null,
    startedAt: null,
    duration: 0,
    config: {
        useDelayStart: false,
        delaySeconds: 3,
        useTimestamp: true,
        useIncrement: false,
        currentIncrement: 1,
        baseName: 'recording',
        recordingTag: '',
        createSubfolder: false,
        customSubfolderName: '',
    },
    computed: {
        recordingName: '',
        subfolderName: '',
        fullRecordingPath: '~/freemocap_data/recordings',
    },
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
            state.computed = computeRecordingPath(state.recordingDirectory, state.config);
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(startRecording.fulfilled, (state, action) => {
                state.isRecording = true;
                state.recordingName = action.meta.arg.recordingName;
                state.recordingDirectory = action.meta.arg.recordingDirectory;
                state.startedAt = new Date().toISOString();
                state.duration = 0;
            })
            .addCase(stopRecording.fulfilled, (state) => {
                state.isRecording = false;
                state.recordingName = null;
                state.startedAt = null;
                state.duration = 0;
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
} = recordingSlice.actions;
