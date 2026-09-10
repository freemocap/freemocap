import type {PlaybackManifest, PlaybackMedia} from '@/services/recording/playback-data';
import {createAsyncThunk, createSlice, type PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '@/store/root-state-types';
import {serverUrls} from '@/services';
import type {RecordingStatusSummary} from '@/types/recording-status';
import type {LoadedCalibration} from '@/store/slices/calibration/calibration-slice';

// ---------------------------------------------------------------------------
// Types matching the backend RecordingBundle response
// ---------------------------------------------------------------------------

export interface PlaybackBundle {
    manifest: PlaybackManifest | null;
    errors: Array<{resource: string; item: string; message: string}>;
    media: PlaybackMedia[];
    recordingId: string;
    recordingFps: number | null;
    totalFrames: number | null;
    durationSeconds: number | null;
    videos: {
        preferredSource: string;
        sources: Record<string, {
            available: boolean;
            valid: boolean;
            videoCount: number;
            videos: Array<{
                videoId: string;
                filename: string;
                sizeBytes: number;
                streamUrl: string;
            }>;
        }>;
    };
    calibration: LoadedCalibration | null;
    trackerSchema: Record<string, unknown> | null;
    statusSummary: RecordingStatusSummary | null;
}

export interface PerRecordingPlaybackData {
    requestId: string | null;
    bundle: PlaybackBundle | null;
    isLoading: boolean;
    error: string | null;
    fetchedAt: number | null;
}

export interface PlaybackDataState {
    byRecordingId: Record<string, PerRecordingPlaybackData>;
}

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

const initialState: PlaybackDataState = {
    byRecordingId: {},
};

const emptyEntry = (): PerRecordingPlaybackData => ({
    requestId: null,
    bundle: null,
    isLoading: false,
    error: null,
    fetchedAt: null,
});

function playbackLocationKey(recordingId: string, parent: string | null | undefined): string {
    return JSON.stringify([parent ?? null, recordingId]);
}

// ---------------------------------------------------------------------------
// Thunk
// ---------------------------------------------------------------------------

export const fetchPlaybackBundle = createAsyncThunk<
    PlaybackBundle,
    { recordingId: string; recordingParentDirectory?: string | null },
    { state: RootState; rejectValue: string }
>(
    'playbackData/fetchBundle',
    async ({recordingId, recordingParentDirectory}, {rejectWithValue, signal}) => {
        try {
            const bundleUrl = serverUrls.endpoints.playbackBundle(recordingId);
            const params = new URLSearchParams();
            if (recordingParentDirectory) {
                params.set('recording_parent_directory', recordingParentDirectory);
            }
            const queryString = params.toString();
            const url = queryString ? `${bundleUrl}?${queryString}` : bundleUrl;
            const response = await fetch(url, {signal});
            if (!response.ok) {
                throw new Error(`Bundle fetch failed: ${response.status}`);
            }
            const data = await response.json();

            const baseUrl = serverUrls.getHttpUrl();
            const sources: PlaybackBundle['videos']['sources'] = {};
            for (const [key, source] of Object.entries(data.videos?.sources ?? {}) as [string, any][]) {
                sources[key] = {
                    available: source.available,
                    valid: source.valid,
                    videoCount: source.video_count,
                    videos: (source.videos || []).map((v: any) => ({
                        videoId: v.video_id,
                        filename: v.filename,
                        sizeBytes: v.size_bytes,
                        streamUrl: `${baseUrl}${v.stream_url}`,
                    })),
                };
            }

            return {
                recordingId: data.recording_id,
                manifest: data.manifest,
                errors: data.errors,
                media: data.media,
                recordingFps: data.recording_fps ?? null,
                totalFrames: data.total_frames ?? null,
                durationSeconds: data.duration_seconds ?? null,
                videos: {
                    preferredSource: data.videos.preferred_source,
                    sources,
                },
                calibration: data.calibration ?? null,
                trackerSchema: data.tracker_schema,
                statusSummary: data.status_summary,
            };
        } catch (error) {
            return rejectWithValue(
                error instanceof Error ? error.message : 'Unknown error',
            );
        }
    },
    {
        condition: ({recordingId, recordingParentDirectory}, {getState}) => {
            const state = getState();
            const existing = state.playbackData.byRecordingId[playbackLocationKey(recordingId, recordingParentDirectory)];
            if (existing?.isLoading) return false;
            return true;
        },
    },
);

// ---------------------------------------------------------------------------
// Slice
// ---------------------------------------------------------------------------

export const playbackDataSlice = createSlice({
    name: 'playbackData',
    initialState,
    reducers: {
        recordingPlaybackInvalidated: (state, action: PayloadAction<{recordingId: string; recordingParentDirectory: string}>) => {
            const key = playbackLocationKey(action.payload.recordingId, action.payload.recordingParentDirectory);
            state.byRecordingId[key] = emptyEntry();
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchPlaybackBundle.pending, (state, action) => {
                const id = playbackLocationKey(action.meta.arg.recordingId, action.meta.arg.recordingParentDirectory);
                const prev = state.byRecordingId[id] ?? emptyEntry();
                state.byRecordingId[id] = {...prev, requestId: action.meta.requestId, isLoading: true, error: null};
            })
            .addCase(fetchPlaybackBundle.fulfilled, (state, action) => {
                const id = playbackLocationKey(action.meta.arg.recordingId, action.meta.arg.recordingParentDirectory);
                if (state.byRecordingId[id]?.requestId !== action.meta.requestId) return;
                state.byRecordingId[id] = {
                    requestId: null,
                    bundle: action.payload,
                    isLoading: false,
                    error: null,
                    fetchedAt: Date.now(),
                };
            })
            .addCase(fetchPlaybackBundle.rejected, (state, action) => {
                const id = playbackLocationKey(action.meta.arg.recordingId, action.meta.arg.recordingParentDirectory);
                if (state.byRecordingId[id]?.requestId !== action.meta.requestId) return;
                const prev = state.byRecordingId[id] ?? emptyEntry();
                state.byRecordingId[id] = {
                    ...prev,
                    requestId: null,
                    isLoading: false,
                    error: action.payload ?? 'Failed to fetch playback bundle',
                    fetchedAt: null,
                };
            });
    },
});

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

export const selectPlaybackBundle = (recordingId: string | null | undefined, parent: string | null | undefined) =>
    (state: RootState): PlaybackBundle | null => {
        if (!recordingId) return null;
        return state.playbackData.byRecordingId[playbackLocationKey(recordingId, parent)]?.bundle ?? null;
    };

export const selectPlaybackBundleIsLoading = (recordingId: string | null | undefined, parent: string | null | undefined) =>
    (state: RootState): boolean => {
        if (!recordingId) return false;
        return state.playbackData.byRecordingId[playbackLocationKey(recordingId, parent)]?.isLoading ?? false;
    };

export const selectPlaybackBundleError = (recordingId: string | null, parent: string | null | undefined) =>
    (state: RootState): string | null => recordingId
        ? state.playbackData.byRecordingId[playbackLocationKey(recordingId, parent)]?.error ?? null : null;

export default playbackDataSlice.reducer;
export const {recordingPlaybackInvalidated} = playbackDataSlice.actions;
