import {serverClient, recordingRequest} from '@/services/server/sdk';
import {recordingProcessingUrl} from '@/services/recording/posthoc-processing';
import {createAsyncThunk} from "@reduxjs/toolkit";
import {RootState} from "@/store";
import {selectCalibrationRecordingPath} from "./calibration-slice";
import {getDetailedErrorMessage} from "@/store/slices/thunk-helpers";
import {serverUrls} from "@/services";
import {LoadedCalibrationSchema} from "./calibration-types";
import type {LoadedCalibration} from "./calibration-slice";
import {fetchTaskSnapshot} from "@/store/slices/pipelines/pipelines-thunks";
import {getTimestampString} from "@/store/slices/recording/getTimestampString";
import {pipelineConfigUpdated} from '@/store/slices/realtime/realtime-slice';
import type {RealtimePipelineConfig} from '@/store/slices/realtime/realtime-types';
import {selectActiveRecordingFullPath} from '@/store/slices/active-recording/active-recording-slice';

/** Discover and load as one request so a subsequent manual selection always wins. */
export const loadRecordingCalibrationDefault = createAsyncThunk<
    LoadedCalibration | null, string, {state: RootState; rejectValue: string}
>(
    'calibration/loadRecordingDefault',
    async (directory, {getState, requestId, rejectWithValue}) => {
        const isCurrent = () => getState().calibration.loadRequestId === requestId
            && selectActiveRecordingFullPath(getState()) === directory;
        try {
            const response = await serverClient().responses.calibration_file_options_freemocap_calibration_files_get({query:{recording_directory:directory},});
            if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
            const {recording_path: path}: {recording_path: string | null} = await response.json();
            if (!isCurrent()) throw Object.assign(new Error('Recording selection changed'), {name: 'AbortError'});
            // A recording without a calibration can still use the existing selection.
            const calibration = path ? await readCalibration(path) : getState().calibration.loadedCalibration;
            if (!isCurrent()) throw Object.assign(new Error('Recording selection changed'), {name: 'AbortError'});
            return calibration;
        } catch (error) {
            if (!isCurrent()) throw Object.assign(new Error('Recording selection changed'), {name: 'AbortError'});
            if (error instanceof Error && error.name === 'AbortError') throw error;
            return rejectWithValue(error instanceof Error ? error.message : String(error));
        }
    },
    {condition: (directory, {getState}) => getState().calibration.defaultRecordingPath !== directory},
);

export const loadCalibrationForRecording = createAsyncThunk<
    LoadedCalibration | null,
    { recordingId: string; recordingParentDirectory?: string | null },
    { state: RootState; rejectValue: string }
>(
    'calibration/loadCalibrationForRecording',
    async ({ recordingId, recordingParentDirectory }, { rejectWithValue }) => {
        try {
            const resp = await serverClient().responses.recordings_get_recording_calibration({path:{recording_id:recordingId},query:{recording_parent_directory:recordingParentDirectory},});
            if (resp.status === 404) {
                return null;
            }
            if (!resp.ok) {
                return rejectWithValue(`Calibration fetch failed: ${resp.status}`);
            }
            return LoadedCalibrationSchema.parse(await resp.json());
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
            const existing = getState().calibration.loadedCalibration;
            if (!force && existing && existing.path === path) {
                return existing;
            }
            return await readCalibration(path);
        } catch (error) {
            const msg = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to load calibration TOML:', msg);
            return rejectWithValue(msg);
        }
    }
);

async function readCalibration(path: string): Promise<LoadedCalibration> {
    const response = await serverClient().responses.calibration_content_freemocap_calibration_content_get({query:{path},});
    if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
    return LoadedCalibrationSchema.parse(await response.json());
}

async function readMostRecentCalibration(): Promise<LoadedCalibration | null> {
    const response = await serverClient().responses.most_recent_calibration_freemocap_calibration_most_recent_get();
    if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
    return LoadedCalibrationSchema.nullable().parse(await response.json());
}

export const restoreCalibrationSelection = createAsyncThunk<
    LoadedCalibration | null, void, {state: RootState; rejectValue: string}
>(
    'calibration/restoreSelection',
    async (_, {dispatch, getState, requestId, rejectWithValue}) => {
        try {
            const response = await serverClient().responses.running_pipeline_config_freemocap_realtime_config_get({});
            if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
            const config: RealtimePipelineConfig | null = await response.json();
            if (config === null) return await readMostRecentCalibration();
            if (getState().calibration.loadRequestId !== requestId) return null;
            dispatch(pipelineConfigUpdated(config));
            const path = config.aggregator_config.calibration_toml_path;
            if (path === null) return await readMostRecentCalibration();
            return await readCalibration(path);
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

/** Resolve the live startup default; the calling apply action sends the config. */
export const loadRealtimeCalibrationDefault = createAsyncThunk<
    LoadedCalibration | null, void, {state: RootState; rejectValue: string}
>(
    'calibration/loadRealtimeDefault',
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

            const response = await serverClient().responses.capture_start_calibration_recording({headers: { 'Content-Type': 'application/json' }, body: {
                    calibrationRecordingDirectory,
                    calibrationTaskConfig,
                }});

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


            const response = await serverClient().responses.capture_stop_calibration_recording({headers: { 'Content-Type': 'application/json' }, body: {calibrationTaskConfig}});

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const accepted = await response.json();
            const result = {...accepted, success: true, pipeline_id: accepted.task_id, recording_name: accepted.recording_id};
            console.log('✅ Stopped calibration recording:', result);
            if (result.pipeline_id) {
                void dispatch(fetchTaskSnapshot());
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

            const response = await serverClient().responses.process_recording_freemocap_recordings__recording_id__processing_post({...recordingRequest(calibrationRecordingDirectory),headers: { 'Content-Type': 'application/json' }, body: {kind:'calibration',config:calibrationTaskConfig}});

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const accepted = await response.json();
            const result = {...accepted, success: true, pipeline_id: accepted.task_id, recording_name: accepted.recording_id};
            console.log('✅ Calibration completed:', result);
            if (result.pipeline_id) {
                void dispatch(fetchTaskSnapshot());
            }
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to calibrate recording:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

