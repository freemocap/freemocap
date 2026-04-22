import {createSelector, createSlice, PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '@/store/types';
import {stopRecording} from '@/store/slices/recording/recording-thunks';
import {buildRecordingStructure, RecordingStructure} from './recording-structure';

export type ActiveRecordingOrigin =
    | 'pending-capture'
    | 'just-captured'
    | 'browsed'
    | 'auto-latest';

export interface ActiveRecordingState {
    baseDirectory: string;
    recordingName: string | null;
    origin: ActiveRecordingOrigin | null;
}

const DEFAULT_BASE_DIRECTORY = '~/freemocap_data/recordings';

const initialState: ActiveRecordingState = {
    baseDirectory: DEFAULT_BASE_DIRECTORY,
    recordingName: null,
    origin: null,
};

export interface ActiveRecordingSetPayload {
    recordingName: string;
    origin: ActiveRecordingOrigin;
    baseDirectory?: string;
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
        },
        activeRecordingBaseDirectoryChanged: (state, action: PayloadAction<string>) => {
            state.baseDirectory = action.payload;
        },
        activeRecordingCleared: (state) => {
            state.recordingName = null;
            state.origin = 'pending-capture';
        },
    },
    extraReducers: (builder) => {
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
        });
    },
});

export const {
    activeRecordingSet,
    activeRecordingBaseDirectoryChanged,
    activeRecordingCleared,
} = activeRecordingSlice.actions;

// ==================== Selectors ====================

export const selectActiveRecording = (state: RootState) => state.activeRecording;
export const selectActiveRecordingName = (state: RootState) => state.activeRecording.recordingName;
export const selectActiveRecordingBaseDirectory = (state: RootState) => state.activeRecording.baseDirectory;
export const selectActiveRecordingOrigin = (state: RootState) => state.activeRecording.origin;

export const selectHasActiveRecording = createSelector(
    [selectActiveRecordingName],
    (name): boolean => name !== null && name.length > 0,
);

export const selectActiveRecordingStructure = createSelector(
    [selectActiveRecordingBaseDirectory, selectActiveRecordingName],
    (baseDirectory, recordingName): RecordingStructure | null => {
        if (!recordingName) return null;
        return buildRecordingStructure({baseDirectory, recordingName});
    },
);

export const selectActiveRecordingFullPath = createSelector(
    [selectActiveRecordingStructure],
    (structure): string | null => structure?.fullPath ?? null,
);

export const selectActiveRecordingCalibrationTomlPath = createSelector(
    [selectActiveRecordingStructure],
    (structure): string | null => structure?.calibrationTomlPath ?? null,
);

export const selectActiveRecordingDataParquetPath = createSelector(
    [selectActiveRecordingStructure],
    (structure): string | null => structure?.dataParquetPath ?? null,
);

export const selectActiveRecordingVideosRawDir = createSelector(
    [selectActiveRecordingStructure],
    (structure): string | null => structure?.videosRawDir ?? null,
);

export const selectActiveRecordingVideosAnnotatedDir = createSelector(
    [selectActiveRecordingStructure],
    (structure): string | null => structure?.videosAnnotatedDir ?? null,
);
