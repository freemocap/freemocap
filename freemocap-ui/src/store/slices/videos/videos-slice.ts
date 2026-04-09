import {createSlice, PayloadAction} from '@reduxjs/toolkit';
import {VideoFile, VideosState} from './videos-types';
import {loadVideos, openVideoFile, selectVideoLoadFolder,} from './videos-thunks';


const initialState: VideosState = {
    folder: '',
    files: [],
    selectedFile: null,
    isLoading: false,
    error: null,
    playbackState: {
        isPlaying: false,
        currentTime: 0,
        duration: 0,
        volume: 1,
        playbackRate: 1,
    },
};

export const videosSlice = createSlice({
    name: 'videos',
    initialState,
    reducers: {
        videoFolderSet: (state, action: PayloadAction<string>) => {
            state.folder = action.payload;
        },
        videoFilesSet: (state, action: PayloadAction<VideoFile[]>) => {
            state.files = action.payload;
        },
        videoFileSelected: (state, action: PayloadAction<VideoFile | null>) => {
            state.selectedFile = action.payload;
            if (action.payload) {
                state.playbackState = {
                    ...state.playbackState,
                    isPlaying: false,
                    currentTime: 0,
                    duration: 0,
                };
            }
        },
        playbackStateUpdated: (
            state,
            action: PayloadAction<Partial<VideosState['playbackState']>>
        ) => {
            state.playbackState = { ...state.playbackState, ...action.payload };
        },
        videosCleared: () => initialState,
    },
    extraReducers: (builder) => {
        builder
            // Select folder
            .addCase(selectVideoLoadFolder.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(selectVideoLoadFolder.fulfilled, (state, action) => {
                state.isLoading = false;
                if (action.payload) {
                    state.folder = action.payload.folder;
                    state.files = action.payload.files;
                }
            })
            .addCase(selectVideoLoadFolder.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to select folder';
            })
            // Load videos
            .addCase(loadVideos.pending, (state) => {
                state.isLoading = true;
            })
            .addCase(loadVideos.fulfilled, (state) => {
                state.isLoading = false;
            })
            .addCase(loadVideos.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to load videos';
            })
            // Open video file
            .addCase(openVideoFile.fulfilled, (state, action) => {
                if (!action.payload.success && action.payload.error) {
                    state.error = action.payload.error.message || 'Failed to open video';
                }
            });
    },
});

export const {
    videoFolderSet,
    videoFilesSet,
    videoFileSelected,
    playbackStateUpdated,
    videosCleared,
} = videosSlice.actions;
