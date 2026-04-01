import { createAsyncThunk } from '@reduxjs/toolkit';
import { z } from 'zod';
import { RootState } from '@/store/types';
import {serverUrls} from "@/services";
import { RecordingCompletionData, StopRecordingResponseSchema } from './recording-types';

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

        const response = await fetch(serverUrls.endpoints.startRecording, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

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
        const response = await fetch(serverUrls.endpoints.stopRecording, {
            method: 'GET',
        });

        if (!response.ok) {
            throw new Error(`Failed to stop recording: ${response.statusText}`);
        }

        const data = await response.json();
        // Backend returns a list (one per camera group); take the first
        const results = z.array(StopRecordingResponseSchema).parse(data);
        return results.length > 0 ? results[0] : null;
    }
);
