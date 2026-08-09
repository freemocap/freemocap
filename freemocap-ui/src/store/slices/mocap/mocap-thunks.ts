import {createAsyncThunk} from "@reduxjs/toolkit";
import {RootState} from "@/store";
import {selectMocapRecordingPath} from "./mocap-slice";
import {getDetailedErrorMessage} from "@/store/slices/thunk-helpers";
import {serverUrls} from "@/services";
import {pipelineProgressUpdated, PipelinePhase, PipelineType} from "@/store/slices/pipelines";
import {selectLoadedCalibration} from "@/store/slices/calibration";

function buildPosthocConfig(state: RootState) {
    const { config } = state.mocap;
    const blender = state.blender;
    // Explicit override wins; fall back to the calibration loaded in the calibration panel
    const calibrationTomlPath =
        state.mocap.calibrationTomlPath ?? selectLoadedCalibration(state)?.path ?? null;
    return {
        detectorType: config.detectorType,
        rtmPoseModelName: config.rtmPoseModelName,
        rtmPoseConfidenceThreshold: config.rtmPoseConfidenceThreshold,
        mediapipeModelComplexity: config.mediapipeModelComplexity,
        mediapipeDetectionConfidence: config.mediapipeDetectionConfidence,
        mediapipePresenceConfidence: config.mediapipePresenceConfidence,
        mediapipeTrackingConfidence: config.mediapipeTrackingConfidence,
        mediapipeNumHands: config.mediapipeNumHands,
        mediapipeNumFaces: config.mediapipeNumFaces,
        calibrationTomlPath,
        triangulationConfig: config.triangulation,
        filterConfig: config.posthoc_filter,
        exportToBlender: blender.exportToBlenderEnabled,
        blenderExePath: blender.blenderExePath ?? blender.detectedBlenderExePath,
        autoOpenBlendFile: blender.autoOpenBlendFile,
    };
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
            const mocapRecordingDirectory = selectMocapRecordingPath(state);

            if (!mocapRecordingDirectory) {
                return rejectWithValue('Recording directory is not set');
            }

            const configWithCalibration = buildPosthocConfig(state);

            console.log('🎬 Starting mocap recording with:', {
                mocapRecordingDirectory,
                mocapTaskConfig: configWithCalibration,
            });

            const response = await fetch(serverUrls.endpoints.mocapStartRecording, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mocapRecordingDirectory,
                    mocapTaskConfig: configWithCalibration,
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
    { success: boolean; pipeline_id?: string; recording_name?: string; recording_path?: string },
    void,
    { state: RootState; rejectValue: string }
>(
    'mocap/stopRecording',
    async (_, { getState, rejectWithValue, dispatch }) => {
        try {
            const state = getState();
            const configWithCalibration = buildPosthocConfig(state);

            console.log(`🎬 Stopping mocap recording and starting mocap with: ${JSON.stringify(configWithCalibration, null, 2)}`);

            const response = await fetch(serverUrls.endpoints.mocapStopRecording, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({mocapTaskConfig: configWithCalibration}),
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            console.log('✅ Stopped mocap recording:', result);
            if (result.pipeline_id) {
                dispatch(pipelineProgressUpdated({
                    pipelineId: result.pipeline_id,
                    pipelineType: PipelineType.MOCAP,
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
            console.error('❌ Failed to stop mocap recording:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

export const importVideos = createAsyncThunk<
    { success: boolean; recordingName: string; recordingPath: string; videoCount: number },
    { videoPaths: string[]; recordingName?: string; baseDirectory?: string },
    { state: RootState; rejectValue: string }
>(
    'mocap/importVideos',
    async ({ videoPaths, recordingName, baseDirectory }, { rejectWithValue }) => {
        try {
            const response = await fetch(serverUrls.endpoints.importVideos, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ videoPaths, recordingName, baseDirectory }),
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            console.log('✅ Imported videos:', result);
            return {
                success: result.success,
                recordingName: result.recording_name,
                recordingPath: result.recording_path,
                videoCount: result.video_count,
            };
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to import videos:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

export interface VideoSyncInfo {
    filename: string;
    cameraId: string;
    frameCount: number;
    fps: number;
    durationSeconds: number;
}

export const checkVideoSync = createAsyncThunk<
    { synchronized: boolean; videos: VideoSyncInfo[]; detail: string | null },
    { videoPaths: string[] },
    { state: RootState; rejectValue: string }
>(
    'mocap/checkVideoSync',
    async ({ videoPaths }, { rejectWithValue }) => {
        try {
            const response = await fetch(serverUrls.endpoints.checkVideoSync, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ videoPaths }),
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            return {
                synchronized: result.synchronized,
                videos: (result.videos ?? []).map((video: any) => ({
                    filename: video.filename,
                    cameraId: video.camera_id,
                    frameCount: video.frame_count,
                    fps: video.fps,
                    durationSeconds: video.duration_seconds,
                })),
                detail: result.detail ?? null,
            };
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to check video sync:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

export const processMocapRecording = createAsyncThunk<
    { success: boolean; message?: string; results?: unknown; pipeline_id?: string },
    void,
    { state: RootState; rejectValue: string }
>(
    'mocap/processMocapRecording',
    async (_, { getState, rejectWithValue, dispatch }) => {
        try {
            const state = getState();
            const mocapRecordingDirectory = selectMocapRecordingPath(state);

            if (!mocapRecordingDirectory) {
                return rejectWithValue('No mocap recording path available. Please set a recording directory or record a mocap first.');
            }

            const configWithCalibration = buildPosthocConfig(state);

            console.log('🔧 Processing recording:', {
                mocapRecordingDirectory,
                mocapTaskConfig: configWithCalibration,
            });

            const response = await fetch(serverUrls.endpoints.processMocapRecording, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mocapRecordingDirectory,
                    mocapTaskConfig: configWithCalibration,
                }),
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            console.log('✅ Mocap completed:', result);
            if (result.pipeline_id) {
                dispatch(pipelineProgressUpdated({
                    pipelineId: result.pipeline_id,
                    pipelineType: PipelineType.MOCAP,
                    phase: PipelinePhase.QUEUED,
                    progress: 0,
                    detail: 'Pipeline queued, starting workers...',
                    recordingName: mocapRecordingDirectory?.split(/[/\\]/).pop() ?? '',
                    recordingPath: mocapRecordingDirectory ?? '',
                }));
            }
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to process recording:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);
