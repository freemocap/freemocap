import {createAsyncThunk} from "@reduxjs/toolkit";
import {RootState} from "@/store";
import {serverUrls} from "@/hooks/server-urls";
import {selectMocapRecordingPath} from "./mocap-slice";

// Helper function to extract detailed error info from failed responses
async function getDetailedErrorMessage(response: Response): Promise<string> {
    let errorDetails: unknown;

    try {
        // Try to parse JSON error response
        errorDetails = await response.json();
        console.error('❌ Server returned validation/error details:', errorDetails);
    } catch {
        // If not JSON, try to get text
        try {
            errorDetails = await response.text();
            console.error('❌ Server returned error text:', errorDetails);
        } catch {
            console.error('❌ Could not read error response body');
        }
    }

    // Build comprehensive error message
    const baseError = `HTTP ${response.status}: ${response.statusText}`;

    if (errorDetails) {
        // Pretty print the error details
        const detailsStr = typeof errorDetails === 'string'
            ? errorDetails
            : JSON.stringify(errorDetails, null, 2);
        return `${baseError}\n\nValidation/Error Details:\n${detailsStr}`;
    }

    return baseError;
}

// Helper function to generate mocap recording name based on recording config
function generateMocapRecordingName(state: RootState): string {
    const recordingConfig = state.recording.config;
    const parts: string[] = [];

    // Add base name if configured
    if (recordingConfig.baseName && recordingConfig.baseName !== 'recording') {
        parts.push(recordingConfig.baseName);
    }

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    parts.push(timestamp);

    // Add recording tag if provided
    if (recordingConfig.recordingTag) {
        parts.push(recordingConfig.recordingTag);
    }

    parts.push('mocap');

    return parts.join('_');
}

export const startMocapRecording = createAsyncThunk<
    { success: boolean; message?: string; mocapRecordingPath?: string },
    void,
    { state: RootState; rejectValue: string }
>(
    'mocap/startRecording',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState();
            const mocapTaskConfig = state.mocap.config;
            const mocapRecordingDirectory = selectMocapRecordingPath(state);

            if (!mocapRecordingDirectory) {
                return rejectWithValue('Recording directory is not set');
            }

            console.log('🎬 Starting mocap recording with:', {
                mocapRecordingDirectory,
                mocapTaskConfig,
            });

            const response = await fetch(serverUrls.endpoints.mocapStartRecording, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mocapRecordingDirectory,
                    mocapTaskConfig,
                }),
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            console.log('✅ Started mocap recording:', result);
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to start mocap recording:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

export const stopMocapRecording = createAsyncThunk<
    { success: boolean },
    void,
    { state: RootState; rejectValue: string }
>(
    'mocap/stopRecording',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState();
            const mocapTaskConfig = state.mocap.config;


            console.log(`🎬 Stoping mocap recording and starting mocap with: ${JSON.stringify(mocapTaskConfig, null, 2)}`);


            const response = await fetch(serverUrls.endpoints.mocapStopRecording, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({mocapTaskConfig}),
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            console.log('✅ Stopped mocap recording:', result);
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to stop mocap recording:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

export const processMocapRecording = createAsyncThunk<
    { success: boolean; message?: string; results?: unknown },
    void,
    { state: RootState; rejectValue: string }
>(
    'mocap/processMocapRecording',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState();
            const mocapTaskConfig = state.mocap.config;
            const mocapRecordingDirectory = selectMocapRecordingPath(state);

            if (!mocapRecordingDirectory) {
                return rejectWithValue('No mocap recording path available. Please set a recording directory or record a mocap first.');
            }

            console.log('🔧 Calibrating recording:', {
                mocapRecordingDirectory,
                mocapTaskConfig,
            });

            const response = await fetch(serverUrls.endpoints.processMocapRecording, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mocapRecordingDirectory,
                    mocapTaskConfig,
                }),
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            console.log('✅ Mocap completed:', result);
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to process recording:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

export const updateMocapConfigOnServer = createAsyncThunk<
    { success: boolean; message?: string },
    void,
    { state: RootState; rejectValue: string }
>(
    'mocap/updateConfig',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState();
            const config = state.mocap.config;

            console.log('⚙️ Updating mocap config on server:', config);

            const response = await fetch(serverUrls.endpoints.updateMocapConfig, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ config }),
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            console.log('✅ Config updated on server:', result);
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to update config on server:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);
