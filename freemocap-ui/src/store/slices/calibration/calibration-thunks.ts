import {createAsyncThunk} from "@reduxjs/toolkit";
import {RootState} from "@/store";
import {selectCalibrationRecordingPath} from "./calibration-slice";
import {getDetailedErrorMessage} from "@/store/slices/thunk-helpers";
import {serverUrls} from "@/services";
import {electronIpc} from "@/services/electron-ipc/electron-ipc";
import type {LoadedCalibration} from "./calibration-slice";

export const loadCalibrationForRecording = createAsyncThunk<
    LoadedCalibration | null,
    string,
    { state: RootState; rejectValue: string }
>(
    'calibration/loadCalibrationForRecording',
    async (recordingId, { rejectWithValue }) => {
        try {
            const url = `${serverUrls.getHttpUrl()}/freemocap/playback/${encodeURIComponent(recordingId)}/calibration`;
            const resp = await fetch(url);
            if (resp.status === 404) {
                console.warn(`[calibration] No calibration found for recording: ${recordingId}`);
                return null;
            }
            if (!resp.ok) {
                return rejectWithValue(`Calibration fetch failed: ${resp.status}`);
            }
            return (await resp.json()) as LoadedCalibration;
        } catch (error) {
            const msg = error instanceof Error ? error.message : 'Unknown error';
            return rejectWithValue(msg);
        }
    }
);

export const loadCalibrationToml = createAsyncThunk<
    LoadedCalibration | null,
    { path: string; force?: boolean },
    { state: RootState; rejectValue: string }
>(
    'calibration/loadCalibrationToml',
    async ({ path, force }, { getState, rejectWithValue }) => {
        try {
            if (!electronIpc) return null;
            const existing = getState().calibration.loadedCalibration;
            if (!force && existing && existing.path === path) {
                return existing;
            }
            const result = await electronIpc.fileSystem.readCalibrationToml.query({ path });
            return result as LoadedCalibration;
        } catch (error) {
            const msg = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to load calibration TOML:', msg);
            return rejectWithValue(msg);
        }
    }
);

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
