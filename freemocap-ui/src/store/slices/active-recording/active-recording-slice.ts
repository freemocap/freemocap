import {createSelector, createSlice, PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '@/store/types';
import {startRecording, stopRecording} from '@/store/slices/recording/recording-thunks';
import {buildRecordingStructure, RecordingStructure} from './recording-structure';
import type {RecordingLayoutPresetName} from './layout-presets/layout-presets';
import {loadFromStorage} from '@/store/persistence';

export type ActiveRecordingOrigin =
    | 'pending-capture'
    | 'just-captured'
    | 'browsed'
    | 'auto-latest';

export interface ActiveRecordingState {
    baseDirectory: string;
    recordingName: string | null;
    origin: ActiveRecordingOrigin | null;
    layoutPreset: RecordingLayoutPresetName;
}

const DEFAULT_BASE_DIRECTORY = '~/freemocap_data/recordings';
const DEFAULT_LAYOUT_PRESET: RecordingLayoutPresetName = 'canonical';

interface PersistedActiveRecording {
    recordingName: string | null;
    baseDirectory: string;
    layoutPreset: RecordingLayoutPresetName;
}

const _persisted = loadFromStorage<PersistedActiveRecording | null>('activeRecording', null);

const initialState: ActiveRecordingState = {
    baseDirectory: _persisted?.baseDirectory ?? DEFAULT_BASE_DIRECTORY,
    recordingName: _persisted?.recordingName ?? null,
    // Normalize origin on restore — 'just-captured' and 'auto-latest' are transient
    origin: _persisted?.recordingName ? 'browsed' : null,
    layoutPreset: _persisted?.layoutPreset ?? DEFAULT_LAYOUT_PRESET,
};

export interface ActiveRecordingSetPayload {
    recordingName: string;
    origin: ActiveRecordingOrigin;
    baseDirectory?: string;
    layoutPreset?: RecordingLayoutPresetName;
}

export const splitParentAndName = (fullPath: string): {baseDirectory: string; recordingName: string} | null => {
    const normalized = fullPath.replace(/\\/g, '/').replace(/\/+$/, '');
    const lastSlash = normalized.lastIndexOf('/');
    if (lastSlash <= 0) return null;
    return {
        baseDirectory: normalized.substring(0, lastSlash),
        recordingName: normalized.substring(lastSlash + 1),
    };
};

export const activeRecordingSlice = createSlice({
    name: 'activeRecording',
    initialState,
    reducers: {
        activeRecordingSet: (state, action: PayloadAction<ActiveRecordingSetPayload>) => {
            state.recordingName = action.payload.recordingName;
            state.origin = action.payload.origin;
            if (action.payload.baseDirectory) {
                state.baseDirectory = action.payload.baseDirectory;
            }
            state.layoutPreset = action.payload.layoutPreset ?? DEFAULT_LAYOUT_PRESET;
        },
        activeRecordingBaseDirectoryChanged: (state, action: PayloadAction<string>) => {
            state.baseDirectory = action.payload;
        },
        activeRecordingLayoutSet: (state, action: PayloadAction<RecordingLayoutPresetName>) => {
            state.layoutPreset = action.payload;
        },
        activeRecordingCleared: (state) => {
            state.recordingName = null;
            state.origin = 'pending-capture';
            state.layoutPreset = DEFAULT_LAYOUT_PRESET;
        },
    },
    extraReducers: (builder) => {
        // Clear active recording as soon as a new capture begins so playback doesn't show stale data
        builder.addCase(startRecording.pending, (state) => {
            state.recordingName = null;
            state.origin = 'pending-capture';
            state.layoutPreset = DEFAULT_LAYOUT_PRESET;
        });

        builder.addCase(stopRecording.fulfilled, (state, action) => {
            if (!action.payload) return;
            const parsed = splitParentAndName(action.payload.recording_path);
            if (parsed) {
                state.baseDirectory = parsed.baseDirectory;
                state.recordingName = parsed.recordingName;
            } else {
                state.recordingName = action.payload.recording_name;
            }
            state.origin = 'just-captured';
            state.layoutPreset = DEFAULT_LAYOUT_PRESET;
        });
    },
});

export const {
    activeRecordingSet,
    activeRecordingBaseDirectoryChanged,
    activeRecordingLayoutSet,
    activeRecordingCleared,
} = activeRecordingSlice.actions;

// ==================== Selectors ====================

export const selectActiveRecording = (state: RootState) => state.activeRecording;
export const selectActiveRecordingName = (state: RootState) => state.activeRecording.recordingName;
export const selectActiveRecordingBaseDirectory = (state: RootState) => state.activeRecording.baseDirectory;
export const selectActiveRecordingOrigin = (state: RootState) => state.activeRecording.origin;
export const selectActiveRecordingLayoutPreset = (state: RootState) => state.activeRecording.layoutPreset;

export const selectHasActiveRecording = createSelector(
    [selectActiveRecordingName],
    (name): boolean => name !== null && name.length > 0,
);

export const selectActiveRecordingStructure = createSelector(
    [selectActiveRecordingBaseDirectory, selectActiveRecordingName, selectActiveRecordingLayoutPreset],
    (baseDirectory, recordingName, layoutPreset): RecordingStructure | null => {
        if (!recordingName) return null;
        return buildRecordingStructure({baseDirectory, recordingName}, {preset: layoutPreset});
    },
);

export const selectActiveRecordingFullPath = createSelector(
    [selectActiveRecordingStructure],
    (structure): string | null => structure?.fullPath ?? null,
);

export const selectEffectiveRecordingPath = createSelector(
    [selectActiveRecordingFullPath],
    (activePath): string | null => activePath ?? null,
);

export const selectActiveRecordingCalibrationTomlPath = createSelector(
    [selectActiveRecordingStructure],
    (structure): string | null => structure?.calibrationTomlPath ?? null,
);

export const selectActiveRecordingDataParquetPath = createSelector(
    [selectActiveRecordingStructure],
    (structure): string | null => structure?.dataParquetPath ?? null,
);

export const selectActiveRecordingVideosSynchronizedDir = createSelector(
    [selectActiveRecordingStructure],
    (structure): string | null => structure?.videosSynchronizedDir ?? null,
);

export const selectActiveRecordingVideosAnnotatedDir = createSelector(
    [selectActiveRecordingStructure],
    (structure): string | null => structure?.videosAnnotatedDir ?? null,
);
