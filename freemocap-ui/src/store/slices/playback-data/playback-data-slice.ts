import {createAsyncThunk, createSlice} from '@reduxjs/toolkit';
import {RootState} from '@/store/types';
import {serverUrls} from '@/services';
import type {RecordingStatusSummary} from '@/types/recording-status';
import type {LoadedCalibration} from '@/store/slices/calibration/calibration-slice';

// ---------------------------------------------------------------------------
// Types matching the backend RecordingBundle response
// ---------------------------------------------------------------------------

export interface PlaybackBundle {
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
    timestamps: {
        timestamps?: Record<string, number[]>;
        warnings?: string[];
    };
    calibration: LoadedCalibration | null;
    trackerSchema: Record<string, unknown>;
    statusSummary: RecordingStatusSummary;
}

export interface PerRecordingPlaybackData {
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
    bundle: null,
    isLoading: false,
    error: null,
    fetchedAt: null,
});

// ---------------------------------------------------------------------------
// Thunk
// ---------------------------------------------------------------------------

export const fetchPlaybackBundle = createAsyncThunk<
    PlaybackBundle,
    { recordingId: string; recordingParentDirectory?: string | null },
    { state: RootState; rejectValue: string }
>(
    'playbackData/fetchBundle',
    async ({recordingId, recordingParentDirectory}, {rejectWithValue}) => {
        try {
            const bundleUrl = serverUrls.endpoints.playbackBundle(recordingId);
            const params = new URLSearchParams();
            if (recordingParentDirectory) {
                params.set('recording_parent_directory', recordingParentDirectory);
            }
            const queryString = params.toString();
            const url = queryString ? `${bundleUrl}?${queryString}` : bundleUrl;
            const response = await fetch(url);
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
                recordingFps: data.recording_fps ?? null,
                totalFrames: data.total_frames ?? null,
                durationSeconds: data.duration_seconds ?? null,
                videos: {
                    preferredSource: data.videos.preferred_source,
                    sources,
                },
                timestamps: data.timestamps ?? {},
                calibration: data.calibration ?? null,
                trackerSchema: data.tracker_schema ?? {
                    name: 'fallback',
                    tracker_type: 'unknown',
                    tracked_points: [],
                    connections: [],
                    landmark_schema: 'generic',
                },
                statusSummary: data.status_summary ?? {},
            };
        } catch (error) {
            return rejectWithValue(
                error instanceof Error ? error.message : 'Unknown error',
            );
        }
    },
    {
        condition: ({recordingId}, {getState}) => {
            const state = getState();
            const existing = state.playbackData.byRecordingId[recordingId];
            if (existing?.bundle || existing?.isLoading) return false;
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
    reducers: {},
    extraReducers: (builder) => {
        builder
            .addCase(fetchPlaybackBundle.pending, (state, action) => {
                const id = action.meta.arg.recordingId;
                const prev = state.byRecordingId[id] ?? emptyEntry();
                state.byRecordingId[id] = {...prev, isLoading: true, error: null};
            })
            .addCase(fetchPlaybackBundle.fulfilled, (state, action) => {
                const id = action.payload.recordingId;
                state.byRecordingId[id] = {
                    bundle: action.payload,
                    isLoading: false,
                    error: null,
                    fetchedAt: Date.now(),
                };
            })
            .addCase(fetchPlaybackBundle.rejected, (state, action) => {
                const id = action.meta.arg.recordingId;
                const prev = state.byRecordingId[id] ?? emptyEntry();
                state.byRecordingId[id] = {
                    ...prev,
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

export const selectPlaybackBundle = (recordingId: string | null | undefined) =>
    (state: RootState): PlaybackBundle | null => {
        if (!recordingId) return null;
        return state.playbackData.byRecordingId[recordingId]?.bundle ?? null;
    };

export const selectPlaybackBundleIsLoading = (recordingId: string | null | undefined) =>
    (state: RootState): boolean => {
        if (!recordingId) return false;
        return state.playbackData.byRecordingId[recordingId]?.isLoading ?? false;
    };

export default playbackDataSlice.reducer;
