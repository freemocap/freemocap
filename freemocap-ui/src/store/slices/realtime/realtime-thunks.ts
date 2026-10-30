import {createAsyncThunk} from "@reduxjs/toolkit";
import {RootState, selectRealtimeEnabledCameraConfigs, selectSelectedCameraConfigs} from "@/store";
import {serverUrls} from "@/services";
import {PipelineApplyResponse, RealtimePipelineConfig} from "@/store/slices/realtime/realtime-types";
import {selectCalibrationConfig, selectLoadedCalibration} from "@/store/slices/calibration/calibration-slice";
import {loadRealtimeCalibrationDefault} from '@/store/slices/calibration/calibration-thunks';

export const applyRealtimePipeline = createAsyncThunk<
    PipelineApplyResponse,
    RealtimePipelineConfig,
    { state: RootState }
>(
    'realtime/apply',
    async (realtimeConfig, {getState, dispatch}) => {
        if (getState().calibration.loadRequestId) throw new Error('Wait for the selected calibration to finish loading.');
        // Null is the product's default-calibration selection. The backend also
        // resolves null independently; load it here to keep the displayed file
        // and board definition in agreement before submitting the live config.
        if (!selectLoadedCalibration(getState())) {
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
        if (getState().calibration.loadRequestId) throw new Error('Wait for the selected calibration to finish loading.');
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

        const configWithBoard: RealtimePipelineConfig = {
            ...realtimeConfig,
            camera_node_config: {
                ...realtimeConfig.camera_node_config,
                charuco_board: liveBoard,
            },
            aggregator_config: {
                ...realtimeConfig.aggregator_config,
                calibration_toml_path: calibrationTomlPath,
            },
        };

        const response = await fetch(serverUrls.endpoints.realtimeConnectOrUpdate, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                realtimeConfig: configWithBoard,
                cameraConfigs,
                realtimeCameraIds,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(`Failed to apply realtime: ${error.detail || response.statusText}`);
        }

        return response.json() as Promise<PipelineApplyResponse>;
    }
);

export const closePipeline = createAsyncThunk<void, void, { state: RootState }>(
    'realtime/close',
    async () => {
        const response = await fetch(serverUrls.endpoints.realtimeClose, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`Failed to close realtime: ${response.statusText}`);
        }
    }
);

export const resetSkeletonFitter = createAsyncThunk<void, void, { state: RootState }>(
    'realtime/resetSkeletonFitter',
    async () => {
        const response = await fetch(serverUrls.endpoints.resetSkeletonFitter, {
            method: 'POST',
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(`Failed to reset skeleton fitter: ${error.detail || response.statusText}`);
        }
    }
);
