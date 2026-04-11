import {createAsyncThunk} from "@reduxjs/toolkit";
import {RootState} from "@/store";
import {selectCalibrationRecordingPath} from "./calibration-slice";
import {getDetailedErrorMessage} from "@/store/slices/thunk-helpers";
import {serverUrls} from "@/services";

export const startCalibrationRecording = createAsyncThunk<
    { success: boolean; message?: string; calibrationRecordingPath?: string },
    void,
    { state: RootState; rejectValue: string }
>(
    'calibration/startRecording',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState();
            const calibrationTaskConfig = state.calibration.config;
            const calibrationRecordingDirectory = selectCalibrationRecordingPath(state);

            if (!calibrationRecordingDirectory) {
                return rejectWithValue('Recording directory is not set');
            }

            console.log('🎬 Starting calibration recording with:', {
                calibrationRecordingDirectory,
                calibrationTaskConfig,
            });

            const response = await fetch(serverUrls.endpoints.calibrationStartRecording, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    calibrationRecordingDirectory,
                    calibrationTaskConfig,
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
    { state: RootState; rejectValue: string }
>(
    'calibration/stopRecording',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState();
            const calibrationTaskConfig = state.calibration.config;


            console.log(`🎬 Stoping calibration recording and starting calibration with: ${JSON.stringify(calibrationTaskConfig, null, 2)}`);


            const response = await fetch(serverUrls.endpoints.calibrationStopRecording, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({calibrationTaskConfig}),
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
            const calibrationTaskConfig = state.calibration.config;
            const calibrationRecordingDirectory = selectCalibrationRecordingPath(state);


            console.log('🔧 Calibrating recording:', {
                calibrationRecordingDirectory,
                calibrationTaskConfig,
            });

            const response = await fetch(serverUrls.endpoints.calibrateRecording, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    calibrationRecordingDirectory,
                    calibrationTaskConfig,
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
