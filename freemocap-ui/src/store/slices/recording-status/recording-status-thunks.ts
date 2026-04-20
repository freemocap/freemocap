import {createAsyncThunk} from '@reduxjs/toolkit';
import {RootState} from '@/store/types';
import {serverUrls} from '@/services';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';
import {RecordingStatus} from '@/types/recording-status';

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
