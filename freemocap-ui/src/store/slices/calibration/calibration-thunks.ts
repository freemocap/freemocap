import { createAsyncThunk } from "@reduxjs/toolkit";
import { RootState } from "@/store";
import { serverUrls } from "@/hooks/server-urls";
import { selectCalibrationRecordingPath } from "./calibration-slice";

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

// Helper function to generate calibration recording name based on recording config
function generateCalibrationRecordingName(state: RootState): string {
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

    parts.push('calibration');

    return parts.join('_');
}

export const startCalibrationRecording = createAsyncThunk<
    { success: boolean; message?: string; calibrationRecordingPath?: string },
    void,
    { state: RootState; rejectValue: string }
>(
    'calibration/startRecording',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState();
            const config = state.calibration.config;
            const calibrationRecordingDirectory = selectCalibrationRecordingPath(state);
            const calibrationRecordingName = generateCalibrationRecordingName(state);

            if (!calibrationRecordingDirectory) {
                return rejectWithValue('Recording directory is not set');
            }

            console.log('🎬 Starting calibration recording with:', {
                calibrationRecordingDirectory,
                calibrationRecordingName,
                config,
            });

            const response = await fetch(serverUrls.endpoints.calibrationStartRecording, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    calibrationRecordingDirectory,
                    calibrationRecordingName,
                    config,
                }),
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            console.log('✅ Started calibration recording:', result);
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to start calibration recording:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

export const stopCalibrationRecording = createAsyncThunk<
    { success: boolean },
    void,
    { rejectValue: string }
>(
    'calibration/stopRecording',
    async (_, { rejectWithValue }) => {
        try {
            console.log('⏹️ Stopping calibration recording...');

            const response = await fetch(serverUrls.endpoints.calibrationStopRecording, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            console.log('✅ Stopped calibration recording:', result);
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to stop calibration recording:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

export const calibrateRecording = createAsyncThunk<
    { success: boolean; message?: string; results?: unknown },
    void,
    { state: RootState; rejectValue: string }
>(
    'calibration/calibrateRecording',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState();
            const config = state.calibration.config;
            const calibrationRecordingPath = selectCalibrationRecordingPath(state);

            if (!calibrationRecordingPath) {
                return rejectWithValue('No calibration recording path available. Please set a recording directory or record a calibration first.');
            }

            console.log('🔧 Calibrating recording:', {
                calibrationRecordingPath,
                config,
            });

            const response = await fetch(serverUrls.endpoints.calibrateRecording, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    calibrationRecordingPath,
                    config,
                }),
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            console.log('✅ Calibration completed:', result);
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to calibrate recording:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

export const updateCalibrationConfigOnServer = createAsyncThunk<
    { success: boolean; message?: string },
    void,
    { state: RootState; rejectValue: string }
>(
    'calibration/updateConfig',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState();
            const config = state.calibration.config;

            console.log('⚙️ Updating calibration config on server:', config);

            const response = await fetch(serverUrls.endpoints.updateCalibrationConfig, {
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
