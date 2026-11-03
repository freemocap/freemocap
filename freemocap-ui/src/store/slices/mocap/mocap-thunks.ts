import {serverClient, recordingRequest} from '@/services/server/sdk';
import {recordingProcessingUrl} from '@/services/recording/posthoc-processing';
import {dlcPosthocExecutionSettings} from './dlc-execution-settings';
import {createAsyncThunk} from "@reduxjs/toolkit";
import type {RootState} from "@/store";
import {selectMocapRecordingPath} from "./mocap-slice";
import {getDetailedErrorMessage} from "@/store/slices/thunk-helpers";
import {serverUrls} from "@/constants/server-urls";
import {fetchTaskSnapshot} from "@/store/slices/pipelines/pipelines-thunks";
import {selectLoadedCalibration} from "@/store/slices/calibration";

import type {StageSelection} from '@/services/recording/posthoc-processing';

function buildPosthocConfig(state: RootState) {
    const { config } = state.mocap;
    const blender = state.blender;
    if (config.detectorType !== 'dlc' && state.calibration.loadRequestId) throw new Error('Wait for the selected calibration to finish loading.');
    const calibrationTomlPath = selectLoadedCalibration(state)?.path ?? null;
    return {
        bodyAlignment: {
            mode: config.bodyAlignmentMode,
            additional_transform: config.referenceTransformEnabled && config.referenceTransform
                ? {matrix: config.referenceTransform}
                : null,
        },
        cameraMatching: config.cameraMatching,
        anchorSegmentName: config.anchorSegmentName,
        exportTallCsv: config.exportTallCsv ?? false,
        exportOptions: {
            formats: config.exportAfterProcessing ? (config.exportFormats ?? []) : [],
            data: config.exportChannels ?? ['LANDMARKS_3D'],
            ...(config.exportChannelOverrides ? {wide_csv: config.exportChannelOverrides} : {}),
        },
        charucoTrackingEnabled: config.charucoTrackingEnabled,
        boardMode: state.calibration.config.boardMode,
        charucoBoard: state.calibration.config.charucoBoard,
        detectorType: config.detectorType,
        dlcModelPath: config.dlcModelPath,
        dlcConfidenceThreshold: config.dlcConfidenceThreshold,
        rtmPoseModelName: config.rtmPoseModelName,
        rtmPoseConfidenceThreshold: config.rtmPoseConfidenceThreshold,
        executionProvider: config.executionProvider,
        mediapipeModelComplexity: config.mediapipeModelComplexity,
        mediapipeDetectionConfidence: config.mediapipeDetectionConfidence,
        mediapipePresenceConfidence: config.mediapipePresenceConfidence,
        mediapipeTrackingConfidence: config.mediapipeTrackingConfidence,
        mediapipeNumHands: config.mediapipeNumHands,
        mediapipeNumFaces: config.mediapipeNumFaces,
        calibrationTomlPath,
        triangulationConfig: {
            useOutlierRejection: config.triangulation.use_outlier_rejection,
            minimumCamerasForTriangulation: config.triangulation.minimum_cameras_for_triangulation,
            maximumCamerasToDrop: config.triangulation.maximum_cameras_to_drop,
            targetReprojectionError: config.triangulation.target_reprojection_error,
        },
        filterConfig: {
            enabled: config.posthoc_filter.enabled,
            method: config.posthoc_filter.method,
            cutoff: config.posthoc_filter.cutoff,
            order: config.posthoc_filter.order,
        },
        // A user run without a Blender executable on the server skips Blender; the Blender node says why.
        exportToBlender: blender.exportToBlenderEnabled && Boolean(blender.blenderExePath ?? blender.detectedBlenderExePath),
        blenderImportRoute: blender.importRoute,
        blenderPackage: blender.packageName,
        blenderDevelopmentBuildHash: blender.developmentBuildHash,
        blenderExportConfig: blender.exportConfig,
        blenderExePath: blender.blenderExePath ?? blender.detectedBlenderExePath,
        autoOpenBlendFile: blender.autoOpenBlendFile,
        ...dlcPosthocExecutionSettings(config.detectorType, config.dlcExecutionProvider),
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

            const response = await serverClient().responses.capture_start_mocap_recording({headers: { 'Content-Type': 'application/json' }, body: {
                    mocapRecordingDirectory,
                    mocapTaskConfig: configWithCalibration,
                }});

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

            const response = await serverClient().responses.capture_stop_mocap_recording({headers: { 'Content-Type': 'application/json' }, body: {mocapTaskConfig: configWithCalibration}});

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const accepted = await response.json();
            const result = {...accepted, success: true, pipeline_id: accepted.task_id, recording_name: accepted.recording_id};
            console.log('✅ Stopped mocap recording:', result);
            if (result.pipeline_id) {
                void dispatch(fetchTaskSnapshot());
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
    { videoPaths: string[]; recordingName?: string; baseDirectory?: string; syncJobId?: string },
    { state: RootState; rejectValue: string }
>(
    'mocap/importVideos',
    async ({ videoPaths, recordingName, baseDirectory, syncJobId }, { rejectWithValue }) => {
        try {
            const response = await serverClient().responses.import_recording({headers: { 'Content-Type': 'application/json' }, body: { videoPaths, recordingName, baseDirectory, syncJobId }});

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
            const response = await serverClient().responses.check_import_frame_counts({headers: { 'Content-Type': 'application/json' }, body: { videoPaths }});

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            return {
                synchronized: result.synchronized,
                videos: (result.videos ?? []).map((video: any) => ({
                    filename: video.filename,
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

export const SyncMethod = {
    AUDIO: 'audio cross-correlation',
    BRIGHTNESS: 'brightness change detection',
} as const;
export type SyncMethod = (typeof SyncMethod)[keyof typeof SyncMethod];

export interface SyncLagResult {
    videoName: string;
    lagSeconds: number;
    confidence: number | null;
}

export interface SyncResult {
    synchronizedVideoFolderPath: string;
    lags: SyncLagResult[];
    elapsedSeconds: number;
    synchronizedFrameCount: number | null;
}

export const startVideoSync = createAsyncThunk<
    { jobId: string },
    { videoPaths: string[]; method: SyncMethod; brightnessRatioThreshold?: number },
    { state: RootState; rejectValue: string }
>(
    'mocap/startVideoSync',
    async ({ videoPaths, method, brightnessRatioThreshold }, { rejectWithValue }) => {
        try {
            const response = await serverClient().responses.synchronize_freemocap_recording_import_synchronize_post({headers: { 'Content-Type': 'application/json' }, body: { videoPaths, method, brightnessRatioThreshold }});

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            return { jobId: result.job_id };
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to start video sync:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

// Poll the common task state; completion includes the synchronization result.
export const getSyncResult = createAsyncThunk<
    { status: 'pending' } | { status: 'done'; result: SyncResult },
    { jobId: string },
    { state: RootState; rejectValue: string }
>(
    'mocap/getSyncResult',
    async ({ jobId }, { rejectWithValue }) => {
        try {
            const response = await serverClient().responses.get_task_freemocap_tasks__task_id__get({path:{task_id:`sync:${jobId}`},});

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const task = await response.json();
            if (task.status === 'queued' || task.status === 'running') return {status: 'pending' as const};
            if (task.status !== 'complete' || !task.result) return rejectWithValue(task.error ?? task.progress.detail);
            const result = task.result;
            return {
                status: 'done' as const,
                result: {
                    synchronizedVideoFolderPath: result.synchronized_video_folder_path,
                    lags: (result.lags ?? []).map((lag: any) => ({
                        videoName: lag.video_name,
                        lagSeconds: lag.lag_seconds,
                        confidence: lag.confidence ?? null,
                    })),
                    elapsedSeconds: result.elapsed_seconds,
                    synchronizedFrameCount: result.synchronized_frame_count ?? null,
                },
            };
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to get sync result:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

/** The mocap processing configuration sent by Process and by the plan preview: one source for both. */
export function mocapProcessingConfig(state: RootState, selection: StageSelection | void) {
    return {...buildPosthocConfig(state), ...selection,
        ...dlcPosthocExecutionSettings(state.mocap.config.detectorType, state.mocap.config.dlcExecutionProvider)};
}

export const processMocapRecording = createAsyncThunk<
    { success: boolean; message?: string; results?: unknown; pipeline_id?: string },
    StageSelection | void,
    { state: RootState; rejectValue: string }
>(
    'mocap/processMocapRecording',
    async (selection, { getState, rejectWithValue, dispatch }) => {
        try {
            const state = getState();
            const mocapRecordingDirectory = selectMocapRecordingPath(state);

            if (!mocapRecordingDirectory) {
                return rejectWithValue('No mocap recording path available. Please set a recording directory or record a mocap first.');
            }

            const config = mocapProcessingConfig(state, selection);

            console.log('🔧 Processing recording:', {mocapRecordingDirectory, mocapTaskConfig: config});

            const response = await serverClient().responses.process_recording_freemocap_recordings__recording_id__processing_post({...recordingRequest(mocapRecordingDirectory),headers: { 'Content-Type': 'application/json' }, body: {
                    kind: 'mocap',
                    config,
                }});

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                return rejectWithValue(errorMessage);
            }

            const accepted = await response.json();
            const result = {...accepted, success: true, pipeline_id: accepted.task_id, recording_name: accepted.recording_id};
            console.log('✅ Mocap completed:', result);
            if (result.pipeline_id) {
                void dispatch(fetchTaskSnapshot());
            }
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to process recording:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);

