import {createSlice} from '@reduxjs/toolkit';
import {RootState} from '@/store/types';
import {detectFfmpeg} from './ffmpeg-thunks';

export interface FfmpegState {
    found: boolean | null;
    ffmpegPath: string | null;
    ffprobePath: string | null;
    message: string | null;
    isDetecting: boolean;
    error: string | null;
}

const initialState: FfmpegState = {
    found: null,
    ffmpegPath: null,
    ffprobePath: null,
    message: null,
    isDetecting: false,
    error: null,
};

export const ffmpegSlice = createSlice({
    name: 'ffmpeg',
    initialState,
    reducers: {},
    extraReducers: (builder) => {
        builder
            .addCase(detectFfmpeg.pending, (state) => {
                state.isDetecting = true;
                state.error = null;
            })
            .addCase(detectFfmpeg.fulfilled, (state, action) => {
                state.isDetecting = false;
                state.found = action.payload.found;
                state.ffmpegPath = action.payload.ffmpegPath;
                state.ffprobePath = action.payload.ffprobePath;
                state.message = action.payload.message ?? null;
            })
            .addCase(detectFfmpeg.rejected, (state, action) => {
                state.isDetecting = false;
                state.error = action.payload || 'Failed to detect ffmpeg';
            });
    },
});

export const selectFfmpeg = (state: RootState) => state.ffmpeg;
export const selectFfmpegAvailable = (state: RootState) => state.ffmpeg.found;

export default ffmpegSlice.reducer;
