import {createSlice} from '@reduxjs/toolkit';
import {RootState} from '@/store/types';
import {RecordingStatus} from '@/types/recording-status';
import {fetchRecordingStatus} from './recording-status-thunks';

export interface PerRecordingStatusState {
    status: RecordingStatus | null;
    isLoading: boolean;
    error: string | null;
    fetchedAt: number | null;
}

export interface RecordingStatusState {
    byRecordingId: Record<string, PerRecordingStatusState>;
}

const initialState: RecordingStatusState = {
    byRecordingId: {},
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
            });
    },
});

export const selectRecordingStatusEntry = (recordingId: string | null | undefined) =>
    (state: RootState): PerRecordingStatusState | null => {
        if (!recordingId) return null;
        return state.recordingStatus.byRecordingId[recordingId] ?? null;
    };

export default recordingStatusSlice.reducer;
