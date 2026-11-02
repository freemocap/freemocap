import {serverClient} from '@/services/server/sdk';
import {createAsyncThunk} from "@reduxjs/toolkit";
import {TemporalConfig} from '@/types/temporal-config';
import {requestTemporalSettings} from '@/services/server/temporal-settings';
import {RootState, selectRealtimeEnabledCameraConfigs, selectSelectedCameraConfigs} from "@/store";
import {serverUrls} from "@/services";
import {PipelineApplyResponse, RealtimePipelineConfig} from "@/store/slices/realtime/realtime-types";
import {selectCalibrationConfig, selectLoadedCalibration} from "@/store/slices/calibration/calibration-slice";
import {loadRealtimeCalibrationDefault} from '@/store/slices/calibration/calibration-thunks';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';
import {realtimeExecutionSettings} from './realtime-settings';

export const applyRealtimePipeline = createAsyncThunk<
    PipelineApplyResponse,
    RealtimePipelineConfig,
    { state: RootState }
>(
    'realtime/apply',
    async (realtimeConfig, {getState, dispatch}) => {
        const isDlc = realtimeConfig.camera_node_config.detector_type === 'dlc';
        if (!isDlc && getState().calibration.loadRequestId) throw new Error('Wait for the selected calibration to finish loading.');
        // Null is the product's default-calibration selection. The backend also
        // resolves null independently; load it here to keep the displayed file
        // and board definition in agreement before submitting the live config.
        if (!isDlc && !selectLoadedCalibration(getState())) {
            if (getState().calibration.error) throw new Error(getState().calibration.error!);
            const selection = await dispatch(loadRealtimeCalibrationDefault());
            if (loadRealtimeCalibrationDefault.rejected.match(selection) && !selectLoadedCalibration(getState())) {
                throw new Error(selection.payload ?? selection.error.message ?? 'Could not load the most recent calibration.');
            }
        }
        // The UI's per-camera `selected` / `realtimeEnabled` flags are hints, not gates.
        // When the UI has an explicit camera selection, send it so the server connects
        // (or reconfigures) exactly those cameras alongside the pipeline. When it does
        // not, send `null` for both fields — the server then attaches the pipeline to
        // whatever camera group is already live. Sending `{}` / `[]` here would trip the
        // server's "no valid camera configs" guard instead of falling through to that
        // existing-group path.
        const selectedCameraConfigs = selectSelectedCameraConfigs(getState());
        const cameraConfigs = Object.keys(selectedCameraConfigs).length > 0 ? selectedCameraConfigs : null;
        const realtimeEnabledIds = Object.keys(selectRealtimeEnabledCameraConfigs(getState()));
        const realtimeCameraIds = realtimeEnabledIds.length > 0 ? realtimeEnabledIds : null;
        const calibrationConfig = selectCalibrationConfig(getState());
        if (!isDlc && getState().calibration.loadRequestId) throw new Error('Wait for the selected calibration to finish loading.');
        const selectedCalibration = selectLoadedCalibration(getState());
        const calibrationTomlPath = selectedCalibration?.path ?? null;
        // Automatic calibration may detect a different board than the editable
        // creation settings. Live detections must use the selected file's board.
        const savedBoard = selectedCalibration?.metadata.board;
        const liveBoard = savedBoard ? {
            squares_x: savedBoard.squares_x,
            squares_y: savedBoard.squares_y,
            square_length_mm: savedBoard.square_length_mm,
            marker_length_ratio: savedBoard.marker_length_ratio,
            aruco_dictionary_enum: savedBoard.aruco_dictionary_enum,
        } : calibrationConfig.charucoBoard;

        const configWithBoard = realtimeExecutionSettings({
            ...realtimeConfig,
            camera_node_config: {
                ...realtimeConfig.camera_node_config,
                charuco_board: liveBoard,
            },
            aggregator_config: {
                ...realtimeConfig.aggregator_config,
                calibration_toml_path: calibrationTomlPath,
            },
        }, getState().mocap.config.dlcExecutionProvider ?? 'cpu');

        const response = await serverClient().responses.pipeline_apply_endpoint_freemocap_realtime_apply_post({headers: {'Content-Type': 'application/json'}, body: {
                realtimeConfig: configWithBoard,
                cameraConfigs,
                realtimeCameraIds,
            }});

        if (!response.ok) {
            throw new Error(`Failed to apply realtime: ${await getDetailedErrorMessage(response)}`);
        }

        return response.json() as Promise<PipelineApplyResponse>;
    }
);

export const closePipeline = createAsyncThunk<void, void, { state: RootState }>(
    'realtime/close',
    async () => {
        const response = await serverClient().responses.stop_realtime_pipelines();

        if (!response.ok) {
            throw new Error(`Failed to close realtime: ${await getDetailedErrorMessage(response)}`);
        }
    }
);

export const resetSkeletonFitter = createAsyncThunk<void, void, { state: RootState }>(
    'realtime/resetSkeletonFitter',
    async () => {
        const response = await serverClient().responses.reset_skeleton_fitter_endpoint_freemocap_realtime_reset_skeleton_fitter_post();

        if (!response.ok) {
            throw new Error(`Failed to reset skeleton fitter: ${await getDetailedErrorMessage(response)}`);
        }
    }
);

export const fetchTemporalConfig = createAsyncThunk('realtime/readTemporal', async () => {
    return requestTemporalSettings();
});

export const applyTemporalConfig = createAsyncThunk('realtime/applyTemporal', async (config: TemporalConfig) => {
    return requestTemporalSettings(config);
});
