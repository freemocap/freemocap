import {serverClient} from '@/services/server/sdk';
import {createAsyncThunk} from '@reduxjs/toolkit';
import {z} from 'zod';
import {RootState} from '@/store/root-state-types';
import {serverUrls} from "@/services";
import {RecordingCompletionData, StopRecordingResponseSchema} from './recording-types';

const RecordStartRequestSchema = z.object({
    recording_name: z.string(),
    recording_directory: z.string(),
    mic_device_index: z.number().default(-1),
});

interface StartRecordingParams {
    recordingName: string;
    recordingDirectory: string;
    micDeviceIndex?: number;
}

export const startRecording = createAsyncThunk<
    void,
    StartRecordingParams,
    { state: RootState }
>(
    'recording/start',
    async ({ recordingName, recordingDirectory, micDeviceIndex = -1 }, { getState }) => {
        const state = getState();

        const payload = RecordStartRequestSchema.parse({
            recording_name: recordingName,
            recording_directory: recordingDirectory,
            mic_device_index: micDeviceIndex,
        });

        const response = await serverClient().responses.start_recording_skellycam_camera_group_all_record_start_post({headers: { 'Content-Type': 'application/json' }, body: payload});

        if (!response.ok) {
            throw new Error(`Failed to start recording: ${response.statusText}`);
        }
    }
);

export const stopRecording = createAsyncThunk<
    RecordingCompletionData | null,
    void,
    { state: RootState }
>(
    'recording/stop',
    async () => {
        const response = await serverClient().responses.stop_recording_skellycam_camera_group_all_record_stop_post();

        if (!response.ok) {
            throw new Error(`Failed to stop recording: ${response.statusText}`);
        }

        const data = await response.json();
        // Backend returns a list (one per camera group); take the first
        const results = z.array(StopRecordingResponseSchema).parse(data);
        return results.length > 0 ? results[0] : null;
    }
);
