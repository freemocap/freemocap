import {createAsyncThunk} from '@reduxjs/toolkit';
import {RootState} from '@/store/types';
import {serverUrls} from '@/services';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';
import {RecordingStatus, RecordingStatusSummary} from '@/types/recording-status';
import {RecordingLayoutValidation} from '@/store/slices/active-recording/recording-structure';

export interface RecordingListEntry {
    name: string;
    path: string;
    video_count: number;
    total_size_bytes: number;
    created_timestamp: string | null;
    total_frames: number | null;
    duration_seconds: number | null;
    fps: number | null;
    status_summary: RecordingStatusSummary;
    status: RecordingStatus | null;
    layout_validation: RecordingLayoutValidation | null;
}

export const fetchRecordingStatus = createAsyncThunk<
    { recordingId: string; status: RecordingStatus },
    { recordingId: string; recordingParentDirectory?: string | null },
    { state: RootState; rejectValue: { recordingId: string; error: string } }
>(
    'recordingStatus/fetch',
    async ({recordingId, recordingParentDirectory}, {rejectWithValue}) => {
        try {
            const base = serverUrls.endpoints.playbackRecordingStatus(recordingId);
            const url = recordingParentDirectory
                ? `${base}?recording_parent_directory=${encodeURIComponent(recordingParentDirectory)}`
                : base;
            const response = await fetch(url);
            if (!response.ok) {
                return rejectWithValue({recordingId, error: await getDetailedErrorMessage(response)});
            }
            const status = (await response.json()) as RecordingStatus;
            return {recordingId, status};
        } catch (e) {
            return rejectWithValue({
                recordingId,
                error: e instanceof Error ? e.message : 'Unknown error',
            });
        }
    }
);

export const fetchAllRecordings = createAsyncThunk<
    { recordings: RecordingListEntry[]; fetchedAt: number },
    { recordingParentDirectory?: string | null } | undefined,
    { state: RootState }
>(
    'recordingStatus/fetchAll',
    async (options) => {
        const params = new URLSearchParams();
        if (options?.recordingParentDirectory) {
            params.set('recording_parent_directory', options.recordingParentDirectory);
        }
        const qs = params.toString();
        const url = `${serverUrls.endpoints.playbackRecordings}${qs ? `?${qs}` : ''}`;
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Failed to fetch recordings: ${response.status}`);
        }
        const recordings: RecordingListEntry[] = await response.json();
        return { recordings, fetchedAt: Date.now() };
    }
);
