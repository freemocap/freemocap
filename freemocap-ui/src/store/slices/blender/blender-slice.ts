import {createSlice, PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '@/store/types';
import {detectBlender, exportRecordingToBlender, openRecordingInBlender} from './blender-thunks';

export interface BlenderState {
    blenderExePath: string | null;
    detectedBlenderExePath: string | null;
    exportToBlenderEnabled: boolean;
    autoOpenBlendFile: boolean;
    isExporting: boolean;
    isDetecting: boolean;
    isOpening: boolean;
    lastBlendFilePath: string | null;
    error: string | null;
}

const initialState: BlenderState = {
    blenderExePath: null,
    detectedBlenderExePath: null,
    exportToBlenderEnabled: true,
    autoOpenBlendFile: true,
    isExporting: false,
    isDetecting: false,
    isOpening: false,
    lastBlendFilePath: null,
    error: null,
};

export const blenderSlice = createSlice({
    name: 'blender',
    initialState,
    reducers: {
        blenderExePathChanged: (state, action: PayloadAction<string | null>) => {
            state.blenderExePath = action.payload;
        },
        blenderExePathCleared: (state) => {
            state.blenderExePath = null;
        },
        exportToBlenderToggled: (state, action: PayloadAction<boolean>) => {
            state.exportToBlenderEnabled = action.payload;
        },
        autoOpenBlendFileToggled: (state, action: PayloadAction<boolean>) => {
            state.autoOpenBlendFile = action.payload;
        },
        blenderErrorCleared: (state) => {
            state.error = null;
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(detectBlender.pending, (state) => {
                state.isDetecting = true;
                state.error = null;
            })
            .addCase(detectBlender.fulfilled, (state, action) => {
                state.isDetecting = false;
                state.detectedBlenderExePath = action.payload.blenderExePath ?? null;
            })
            .addCase(detectBlender.rejected, (state, action) => {
                state.isDetecting = false;
                state.error = action.payload || 'Failed to detect Blender';
            });

        builder
            .addCase(exportRecordingToBlender.pending, (state) => {
                state.isExporting = true;
                state.error = null;
            })
            .addCase(exportRecordingToBlender.fulfilled, (state, action) => {
                state.isExporting = false;
                state.lastBlendFilePath = action.payload.blenderFilePath ?? null;
            })
            .addCase(exportRecordingToBlender.rejected, (state, action) => {
                state.isExporting = false;
                state.error = action.payload || 'Failed to export to Blender';
            });

        builder
            .addCase(openRecordingInBlender.pending, (state) => {
                state.isOpening = true;
                state.error = null;
            })
            .addCase(openRecordingInBlender.fulfilled, (state, action) => {
                state.isOpening = false;
                if (action.payload.blendFilePath) {
                    state.lastBlendFilePath = action.payload.blendFilePath;
                }
            })
            .addCase(openRecordingInBlender.rejected, (state, action) => {
                state.isOpening = false;
                state.error = action.payload || 'Failed to open Blender';
            });
    },
});

export const selectBlender = (state: RootState) => state.blender;
export const selectBlenderExePath = (state: RootState) =>
    state.blender.blenderExePath ?? state.blender.detectedBlenderExePath;
export const selectEffectiveBlenderExePath = selectBlenderExePath;
export const selectExportToBlenderEnabled = (state: RootState) => state.blender.exportToBlenderEnabled;
export const selectAutoOpenBlendFile = (state: RootState) => state.blender.autoOpenBlendFile;

export const {
    blenderExePathChanged,
    blenderExePathCleared,
    exportToBlenderToggled,
    autoOpenBlendFileToggled,
    blenderErrorCleared,
} = blenderSlice.actions;

export default blenderSlice.reducer;
