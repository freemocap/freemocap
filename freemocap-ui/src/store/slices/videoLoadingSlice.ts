// skellycam-ui/src/store/slices/videoLoadingSlice.ts
import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface VideoFile {
  name: string;
  path: string;
}

interface VideoLoadingState {
  videoFolder: string;
  videoFiles: VideoFile[];
  isLoading: boolean;
  error: string | null;
}

const initialState: VideoLoadingState = {
  videoFolder: '',
  videoFiles: [],
  isLoading: false,
  error: null,
};

export const videoLoadingSlice = createSlice({
  name: 'videoLoading',
  initialState,
  reducers: {
    setVideoFolder: (state, action: PayloadAction<string>) => {
      state.videoFolder = action.payload;
    },
    setVideoFiles: (state, action: PayloadAction<VideoFile[]>) => {
      state.videoFiles = action.payload;
    },
    setIsLoading: (state, action: PayloadAction<boolean>) => {
      state.isLoading = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
    clearVideoData: (state) => {
      state.videoFolder = '';
      state.videoFiles = [];
      state.error = null;
    },
  },
});

export const {
  setVideoFolder,
  setVideoFiles,
  setIsLoading,
  setError,
  clearVideoData,
} = videoLoadingSlice.actions;

export default videoLoadingSlice.reducer;