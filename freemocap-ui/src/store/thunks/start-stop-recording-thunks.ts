// recording-thunks.ts
import {createAsyncThunk} from '@reduxjs/toolkit';
import {z} from 'zod';
import {setRecordingInfo} from "@/store/slices/recordingInfoSlice";
import {urlService} from "@/config/appUrlService";

const RecordStartRequestSchema = z.object({
    recording_name: z.string(),
    recording_directory: z.string(),
    mic_device_index: z.number().default(-1),
});

type StartRecordingParams = {
    recordingName: string;
    recordingDirectory: string;
};

export const startRecording = createAsyncThunk<void, StartRecordingParams>(
    'appState/startRecording',
    async ({recordingName, recordingDirectory}, {dispatch,}) => {
        console.log(`Starting recording with name: ${recordingName} in directory: ${recordingDirectory}`);
        try {
            const recStartUrl = urlService.getHttpEndpointUrls().startRecording;

            const requestPayload = RecordStartRequestSchema.parse({
                recording_name: recordingName,
                recording_directory: recordingDirectory,

            });
            console.log(`Request payload: ${JSON.stringify(requestPayload, null, 2)}`);
            const response = await fetch(recStartUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestPayload),
            });

            if (response.ok) {
                dispatch(setRecordingInfo({
                    isRecording: true,
                    recordingName,
                    recordingDirectory,
                }));
                console.log('Recording started successfully');
            } else {
                throw new Error(`Failed to start recording: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Recording start failed:', error);
            throw error;
        }
    }
);

export const stopRecording = createAsyncThunk<void, void>(
    'appState/stopRecording',
    async (_, {dispatch}) => {
        console.log('Stopping recording...');
        try {
            const recStopUrl = urlService.getHttpEndpointUrls().stopRecording;
            const response = await fetch(recStopUrl, {
                method: 'GET',
            });

            if (response.ok) {
                dispatch(setRecordingInfo({
                    isRecording: false,
                    recordingName: null,
                }));
                console.log('Recording stopped successfully');
            } else {
                throw new Error(`Failed to stop recording: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Recording stop failed:', error);
            throw error;
        }
    }
);
