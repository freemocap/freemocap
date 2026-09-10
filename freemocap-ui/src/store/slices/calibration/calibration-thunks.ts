import {createAsyncThunk} from "@reduxjs/toolkit";
import {RootState} from "@/store";
import {selectCalibrationRecordingPath} from "./calibration-slice";
import {getDetailedErrorMessage} from "@/store/slices/thunk-helpers";
import {serverUrls} from "@/services";
import {electronIpc} from "@/services/electron-ipc/electron-ipc";
import type {LoadedCalibration} from "./calibration-slice";
import {pipelineProgressUpdated, PipelinePhase, PipelineType} from "@/store/slices/pipelines";
import {getTimestampString} from "@/store/slices/recording/getTimestampString";
import {pipelineConfigUpdated} from '@/store/slices/realtime/realtime-slice';
import type {RealtimePipelineConfig} from '@/store/slices/realtime/realtime-types';

export const checkPyceresAvailability = createAsyncThunk<
    { available: boolean; message?: string | null },
    void,
    { state: RootState; rejectValue: string }
>(
    'calibration/checkPyceresAvailability',
    async (_, { rejectWithValue }) => {
        try {
            const response = await fetch(serverUrls.endpoints.calibrationPyceresAvailability);
            if (!response.ok) {
                return rejectWithValue(await getDetailedErrorMessage(response));
            }
            const data = await response.json();
            return {
                available: !!data.available,
                message: data.message ?? null,
            };
        } catch (error) {
            const msg = error instanceof Error ? error.message : 'Unknown error';
            return rejectWithValue(msg);
        }
    }
);

export const loadCalibrationForRecording = createAsyncThunk<
    LoadedCalibration | null,
    { recordingId: string; recordingParentDirectory?: string | null },
    { state: RootState; rejectValue: string }
>(
    'calibration/loadCalibrationForRecording',
    async ({ recordingId, recordingParentDirectory }, { rejectWithValue }) => {
        try {
            const params = new URLSearchParams();
            if (recordingParentDirectory) {
                params.set('recording_parent_directory', recordingParentDirectory);
            }
            const qs = params.toString();
            const url = `${serverUrls.getHttpUrl()}/freemocap/playback/${encodeURIComponent(recordingId)}/calibration${qs ? `?${qs}` : ''}`;
            const resp = await fetch(url);
            if (resp.status === 404) {
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
            if (!electronIpc) throw new Error('Calibration TOML loading requires the desktop file service.');
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

async function readMostRecentCalibration(): Promise<LoadedCalibration | null> {
    const response = await fetch(`${serverUrls.getHttpUrl()}/freemocap/calibration/most-recent`);
    if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
    const path: unknown = await response.json();
    if (path === null) return null;
    if (typeof path !== 'string' || !path) throw new Error('Invalid most-recent calibration path');
    if (!electronIpc) throw new Error('Calibration TOML loading requires the desktop file service.');
    return await electronIpc.fileSystem.readCalibrationToml.query({path}) as LoadedCalibration;
}

export const restoreCalibrationSelection = createAsyncThunk<
    LoadedCalibration | null, void, {state: RootState; rejectValue: string}
>(
    'calibration/restoreSelection',
    async (_, {dispatch, getState, requestId, rejectWithValue}) => {
        try {
            const response = await fetch(`${serverUrls.getHttpUrl()}/freemocap/realtime/config`);
            if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
            const config: RealtimePipelineConfig | null = await response.json();
            if (config === null) return await readMostRecentCalibration();
            if (getState().calibration.loadRequestId !== requestId) return null;
            dispatch(pipelineConfigUpdated(config));
            const path = config.aggregator_config.calibration_toml_path;
            if (path === null) return null;
            if (!electronIpc) throw new Error('Calibration TOML loading requires the desktop file service.');
            return await electronIpc.fileSystem.readCalibrationToml.query({path}) as LoadedCalibration;
        } catch (error) {
            return rejectWithValue(error instanceof Error ? error.message : String(error));
        }
    },
);

export const loadMostRecentCalibration = createAsyncThunk<
    LoadedCalibration | null, void, {state: RootState; rejectValue: string}
>(
    'calibration/loadMostRecent',
    async (_, {rejectWithValue}) => {
        try {
            return await readMostRecentCalibration();
        } catch (error) {
            return rejectWithValue(error instanceof Error ? error.message : String(error));
        }
    },
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

            // Starting a calibration recording is a NEW capture, so it must mint a fresh
            // timestamped directory — NOT reuse the currently selected/active recording path
            // (that's what `calibrateRecording` does, to re-process an existing recording).
            // Using the active path here let new videos pile into an old recording folder,
            // mixing camera sets / frame counts and breaking posthoc calibration.
            //
            // recordingDirectory is guaranteed non-empty from store initialization onward
            // (see recording-slice.ts) — no need to guard it here.
            const recordingsRoot = state.recording.recordingDirectory;
            const base = recordingsRoot.replace(/[\\/]+$/, '');
            const calibrationRecordingDirectory = `${base}/${getTimestampString()}_calibration`;

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
    { success: boolean; pipeline_id?: string; recording_name?: string; recording_path?: string },
    void,
    { state: RootState; rejectValue: string }
>(
    'calibration/stopRecording',
    async (_, { getState, rejectWithValue, dispatch }) => {
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
            if (result.pipeline_id) {
                dispatch(pipelineProgressUpdated({
                    pipelineId: result.pipeline_id,
                    pipelineType: PipelineType.CALIBRATION,
                    phase: PipelinePhase.QUEUED,
                    progress: 0,
                    detail: 'Pipeline queued, starting workers...',
                    recordingName: result.recording_name ?? '',
                    recordingPath: result.recording_path ?? '',
                }));
            }
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to stop calibration recording:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

export const calibrateRecording = createAsyncThunk<
    { success: boolean; message?: string; results?: unknown; pipeline_id?: string },
    {recordingPath: string},
    { state: RootState; rejectValue: string }
>(
    'calibration/calibrateRecording',
    async ({recordingPath}, { getState, rejectWithValue, dispatch }) => {
        try {
            const state = getState();
            const calibrationTaskConfig = state.calibration.config;
            const calibrationRecordingDirectory = recordingPath;
            if (!recordingPath.trim()) throw new Error("Select a recording to calibrate");


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
            if (result.pipeline_id) {
                dispatch(pipelineProgressUpdated({
                    pipelineId: result.pipeline_id,
                    pipelineType: PipelineType.CALIBRATION,
                    phase: PipelinePhase.QUEUED,
                    progress: 0,
                    detail: 'Pipeline queued, starting workers...',
                    recordingName: calibrationRecordingDirectory?.split(/[/\\]/).pop() ?? '',
                    recordingPath: calibrationRecordingDirectory ?? '',
                }));
            }
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to calibrate recording:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);
