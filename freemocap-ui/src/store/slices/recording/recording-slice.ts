import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { RecordingInfo } from './recording-types';
import { startRecording, stopRecording } from './recording-thunks';

const initialState: RecordingInfo = {
    isRecording: false,
    recordingDirectory: '~/freemocap_data/recordings',
    recordingName: null,
    startedAt: null,
    duration: 0,
    completionData: null,
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
        recordingCompletionDismissed: (state) => {
            state.completionData = null;
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
                state.completionData = null;
            })
            .addCase(stopRecording.fulfilled, (state, action) => {
                state.isRecording = false;
                state.recordingName = null;
                state.startedAt = null;
                state.duration = 0;
                state.completionData = action.payload ?? null;
            });
    },
});

export const {
    recordingInfoUpdated,
    recordingDirectoryChanged,
    recordingDurationUpdated,
    recordingCompletionDismissed,
} = recordingSlice.actions;
