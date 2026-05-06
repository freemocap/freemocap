import {createSlice} from '@reduxjs/toolkit';
import {RootState} from '@/store/types';
import {RecordingStatus} from '@/types/recording-status';
import {fetchRecordingStatus, fetchAllRecordings, RecordingListEntry} from './recording-status-thunks';

export interface PerRecordingStatusState {
    status: RecordingStatus | null;
    isLoading: boolean;
    error: string | null;
    fetchedAt: number | null;
}

export interface RecordingStatusState {
    byRecordingId: Record<string, PerRecordingStatusState>;
    recordingsList: RecordingListEntry[];
    recordingsFetchedAt: number | null;
    recordingsIsLoading: boolean;
}

const initialState: RecordingStatusState = {
    byRecordingId: {},
    recordingsList: [],
    recordingsFetchedAt: null,
    recordingsIsLoading: false,
};

const emptyEntry = (): PerRecordingStatusState => ({
    status: null,
    isLoading: false,
    error: null,
    fetchedAt: null,
});

export const recordingStatusSlice = createSlice({
    name: 'recordingStatus',
    initialState,
    reducers: {},
    extraReducers: (builder) => {
        builder
            .addCase(fetchRecordingStatus.pending, (state, action) => {
                const id = action.meta.arg.recordingId;
                const prev = state.byRecordingId[id] ?? emptyEntry();
                state.byRecordingId[id] = {...prev, isLoading: true, error: null};
            })
            .addCase(fetchRecordingStatus.fulfilled, (state, action) => {
                const {recordingId, status} = action.payload;
                state.byRecordingId[recordingId] = {
                    status,
                    isLoading: false,
                    error: null,
                    fetchedAt: Date.now(),
                };
            })
            .addCase(fetchRecordingStatus.rejected, (state, action) => {
                const id = action.meta.arg.recordingId;
                const prev = state.byRecordingId[id] ?? emptyEntry();
                state.byRecordingId[id] = {
                    ...prev,
                    isLoading: false,
                    error: action.payload?.error ?? 'Failed to fetch recording status',
                };
            })
            .addCase(fetchAllRecordings.pending, (state) => {
                state.recordingsIsLoading = true;
            })
            .addCase(fetchAllRecordings.fulfilled, (state, action) => {
                const {recordings, fetchedAt} = action.payload;
                state.recordingsList = recordings;
                state.recordingsFetchedAt = fetchedAt;
                state.recordingsIsLoading = false;
                // Populate per-recording status entries from the batch response
                for (const rec of recordings) {
                    if (rec.status) {
                        state.byRecordingId[rec.name] = {
                            status: rec.status,
                            isLoading: false,
                            error: null,
                            fetchedAt,
                        };
                    }
                }
            })
            .addCase(fetchAllRecordings.rejected, (state) => {
                state.recordingsIsLoading = false;
            });
    },
});

export const selectRecordingStatusEntry = (recordingId: string | null | undefined) =>
    (state: RootState): PerRecordingStatusState | null => {
        if (!recordingId) return null;
        return state.recordingStatus.byRecordingId[recordingId] ?? null;
    };

export const selectRecordingsList = (state: RootState) =>
    state.recordingStatus.recordingsList;

export const selectRecordingsFetchedAt = (state: RootState) =>
    state.recordingStatus.recordingsFetchedAt;

export const selectRecordingsIsLoading = (state: RootState) =>
    state.recordingStatus.recordingsIsLoading;

export default recordingStatusSlice.reducer;
