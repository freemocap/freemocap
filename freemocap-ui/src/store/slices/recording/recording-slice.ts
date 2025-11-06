import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { RecordingInfo, RecordingConfig } from './recording-types';
import { startRecording, stopRecording } from './recording-thunks';

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
};

export const recordingSlice = createSlice({
    name: 'recording',
    initialState,
    reducers: {
        recordingInfoUpdated: (state, action: PayloadAction<Partial<RecordingInfo>>) => {
            return { ...state, ...action.payload };
        },
        recordingDirectoryChanged: (state, action: PayloadAction<string>) => {
            state.recordingDirectory = action.payload;
        },
        recordingDurationUpdated: (state, action: PayloadAction<number>) => {
            state.duration = action.payload;
        },

        // Config updates
        configUpdated: (state, action: PayloadAction<Partial<RecordingConfig>>) => {
            state.config = { ...state.config, ...action.payload };
        },
        useDelayStartToggled: (state, action: PayloadAction<boolean>) => {
            state.config.useDelayStart = action.payload;
        },
        delaySecondsChanged: (state, action: PayloadAction<number>) => {
            state.config.delaySeconds = action.payload;
        },
        useTimestampToggled: (state, action: PayloadAction<boolean>) => {
            state.config.useTimestamp = action.payload;
        },
        useIncrementToggled: (state, action: PayloadAction<boolean>) => {
            state.config.useIncrement = action.payload;
        },
        currentIncrementChanged: (state, action: PayloadAction<number>) => {
            state.config.currentIncrement = action.payload;
        },
        currentIncrementIncremented: (state) => {
            state.config.currentIncrement += 1;
        },
        baseNameChanged: (state, action: PayloadAction<string>) => {
            state.config.baseName = action.payload;
        },
        recordingTagChanged: (state, action: PayloadAction<string>) => {
            state.config.recordingTag = action.payload;
        },
        createSubfolderToggled: (state, action: PayloadAction<boolean>) => {
            state.config.createSubfolder = action.payload;
        },
        customSubfolderNameChanged: (state, action: PayloadAction<string>) => {
            state.config.customSubfolderName = action.payload;
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
} = recordingSlice.actions;
