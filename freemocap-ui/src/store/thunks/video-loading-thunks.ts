// skellycam-ui/src/store/thunks/video-loading-thunks.ts
import { createAsyncThunk } from '@reduxjs/toolkit';
import { 
  setVideoFolder, 
  setVideoFiles, 
  setIsLoading, 
  setError 
} from '../slices/videoLoadingSlice';

const VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv', '.webm'];
export const selectVideoFolder = createAsyncThunk(
  'videoLoading/selectFolder',
  async (_, { dispatch }) => {
    try {
      dispatch(setIsLoading(true));
      dispatch(setError(null));
      
      const selectedFolder = await window.electronAPI.selectDirectory();

      if (!selectedFolder) {
        return null;
      }
      dispatch(setVideoFolder(selectedFolder));

      const folderContents = await window.electronAPI.getFolderContents(selectedFolder);

      if (folderContents.error) {
        throw new Error(`Failed to read folder contents: ${folderContents.error}`);
      }

      const videoFiles = folderContents.contents
        ?.filter(item =>
          item.isFile &&
          VIDEO_EXTENSIONS.some(ext =>
            item.name.toLowerCase().endsWith(ext)
          )
        )
        .map(file => ({
          name: file.name,
          path: file.path
        })) || [];
      dispatch(setVideoFiles(videoFiles));
      
      return {
        folder: selectedFolder,
        files: videoFiles
      };
    } catch (error) {
      dispatch(setError(error instanceof Error ? error.message : 'Unknown error'));
      throw error;
    } finally {
      dispatch(setIsLoading(false));
    }
  }
);

export const loadVideos = createAsyncThunk(
  'videoLoading/loadVideos',
  async ({ folder, files }: { folder: string, files: { name: string, path: string }[] }, { dispatch }) => {
    try {
      dispatch(setIsLoading(true));
      dispatch(setError(null));
      
      const success = await window.electronAPI.openFolder(folder);

      if (!success) {
        throw new Error('Failed to open folder');
      }
      return { success: true };
    } catch (error) {
      dispatch(setError(error instanceof Error ? error.message : 'Unknown error'));
      throw error;
    } finally {
      dispatch(setIsLoading(false));
    }
  }
);

export const openVideoFile = createAsyncThunk(
  'videoLoading/openVideoFile',
  async (filePath: string, { dispatch }) => {
    try {
      const folderPath = filePath.substring(0, filePath.lastIndexOf('/'));
      await window.electronAPI.openFolder(folderPath);

      return { success: true };
    } catch (error) {
      console.error('Failed to open video file:', error);
      return { success: false, error };
    }
  }
);
