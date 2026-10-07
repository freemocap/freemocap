import {createSlice, PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '@/store/root-state-types';
import {detectBlender, exportRecordingToBlender, openRecordingInBlender} from './blender-thunks';
import {loadFromStorage} from '@/store/persistence';

export type BlenderImportRoute = 'auto' | 'parquet_segments' | 'parquet_constraints' | 'legacy_npy';

export interface BlenderExportConfig {
    formats: ('fbx' | 'bvh')[];
    rest_pose: 'tpose' | 'apose';
    apply_foot_locking: boolean;
    limit_hand_markers_range_of_motion: boolean;
}
export interface BlenderState {
    exportConfig: BlenderExportConfig;
    importRoute: BlenderImportRoute;
    packageName: string | null;
    blenderExePath: string | null;
    detectedBlenderExePath: string | null;
    exportToBlenderEnabled: boolean;
    autoOpenBlendFile: boolean;
    /** Remembers autoOpenBlendFile's value from before exportToBlenderEnabled was turned off, so it can be restored. */
    autoOpenBlendFileBeforeExportDisabled: boolean | null;
    isExporting: boolean;
    isDetecting: boolean;
    hasAttemptedDetection: boolean;
    isOpening: boolean;
    lastBlendFilePath: string | null;
    error: string | null;
}

interface PersistedBlenderSettings {
    exportConfig?: BlenderExportConfig;
    importRoute?: BlenderImportRoute;
    packageName?: string | null;
    blenderExePath: string | null;
    exportToBlenderEnabled: boolean;
    autoOpenBlendFile: boolean;
}

const _persistedBlender = loadFromStorage<PersistedBlenderSettings | null>('blender.settings', null);

const initialState: BlenderState = {
    exportConfig: _persistedBlender?.exportConfig ?? {formats: [], rest_pose: 'tpose', apply_foot_locking: false, limit_hand_markers_range_of_motion: false},
    importRoute: _persistedBlender?.importRoute ?? 'auto',
    packageName: _persistedBlender?.packageName ?? null,
    blenderExePath: _persistedBlender?.blenderExePath ?? null,
    detectedBlenderExePath: null,
    exportToBlenderEnabled: _persistedBlender?.exportToBlenderEnabled ?? true,
    autoOpenBlendFile: _persistedBlender?.autoOpenBlendFile ?? true,
    autoOpenBlendFileBeforeExportDisabled: null,
    isExporting: false,
    isDetecting: false,
    hasAttemptedDetection: false,
    isOpening: false,
    lastBlendFilePath: null,
    error: null,
};

export const blenderSlice = createSlice({
    name: 'blender',
    initialState,
    reducers: {
        blenderImportRouteChanged: (state, action: PayloadAction<BlenderImportRoute>) => { state.importRoute = action.payload;
            if (action.payload !== 'legacy_npy') state.exportConfig.formats = state.exportConfig.formats.filter(f => f !== 'bvh');
            if (action.payload === 'auto' || action.payload === 'parquet_segments') {
                state.exportConfig.rest_pose = 'tpose';
                state.exportConfig.apply_foot_locking = false;
                state.exportConfig.limit_hand_markers_range_of_motion = false;
            } },
        blenderExportConfigUpdated: (state, action: PayloadAction<Partial<BlenderExportConfig>>) => { Object.assign(state.exportConfig, action.payload); },
        blenderPackageChanged: (state, action: PayloadAction<string | null>) => { state.packageName = action.payload; },
        blenderExePathChanged: (state, action: PayloadAction<string | null>) => {
            state.blenderExePath = action.payload;
            state.packageName = null;
        },
        blenderExePathCleared: (state) => {
            state.blenderExePath = null;
            state.packageName = null;
        },
        exportToBlenderToggled: (state, action: PayloadAction<boolean>) => {
            const enabled = action.payload;
            if (!enabled && state.exportToBlenderEnabled) {
                state.autoOpenBlendFileBeforeExportDisabled = state.autoOpenBlendFile;
                state.autoOpenBlendFile = false;
            } else if (enabled && !state.exportToBlenderEnabled && state.autoOpenBlendFileBeforeExportDisabled !== null) {
                state.autoOpenBlendFile = state.autoOpenBlendFileBeforeExportDisabled;
                state.autoOpenBlendFileBeforeExportDisabled = null;
            }
            state.exportToBlenderEnabled = enabled;
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
                state.hasAttemptedDetection = true;
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
    blenderExportConfigUpdated,
    blenderImportRouteChanged,
    blenderPackageChanged,
    blenderExePathChanged,
    blenderExePathCleared,
    exportToBlenderToggled,
    autoOpenBlendFileToggled,
    blenderErrorCleared,
} = blenderSlice.actions;

export default blenderSlice.reducer;
