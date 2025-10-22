import { createSelector } from '@reduxjs/toolkit';
import { RootState } from '../../types';

export const selectVideoFolder = (state: RootState) => state.videos.folder;
export const selectVideoFiles = (state: RootState) => state.videos.files;
export const selectSelectedVideo = (state: RootState) => state.videos.selectedFile;
export const selectVideoPlaybackState = (state: RootState) => state.videos.playbackState;
export const selectVideoLoadingState = (state: RootState) => state.videos.isLoading;
export const selectVideoError = (state: RootState) => state.videos.error;

export const selectVideosByExtension = createSelector(
    [selectVideoFiles, (_: RootState, extension: string) => extension],
    (files, extension) =>
        files.filter((file: { name: string; }) => file.name.toLowerCase().endsWith(extension))
);

export const selectIsVideoPlaying = createSelector(
    [selectVideoPlaybackState],
    (playback) => playback.isPlaying
);
