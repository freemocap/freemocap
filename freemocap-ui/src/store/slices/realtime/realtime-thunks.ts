import {createAsyncThunk} from "@reduxjs/toolkit";
import {RootState, selectRealtimeEnabledCameraConfigs, selectSelectedCameraConfigs} from "@/store";
import {serverUrls} from "@/services";
import {PipelineApplyResponse, RealtimePipelineConfig} from "@/store/slices/realtime/realtime-types";
import {selectCalibrationConfig, selectCalibrationDirectoryInfo} from "@/store/slices/calibration/calibration-slice";

export const applyRealtimePipeline = createAsyncThunk<
    PipelineApplyResponse,
    RealtimePipelineConfig,
    { state: RootState }
>(
    'realtime/apply',
    async (realtimeConfig, {getState}) => {
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
        const calibrationDirectoryInfo = selectCalibrationDirectoryInfo(getState());

        // Auto-inject the last-successful calibration path when none is explicitly set.
        // This ensures the realtime triangulation uses the same calibration the user
        // ran most recently, rather than whatever happens to be on disk when the
        // aggregator process starts.
        const calibrationTomlPath =
            realtimeConfig.aggregator_config.calibration_toml_path
            ?? calibrationDirectoryInfo?.lastSuccessfulCalibrationTomlPath
            ?? null;

        const configWithBoard: RealtimePipelineConfig = {
            ...realtimeConfig,
            camera_node_config: {
                ...realtimeConfig.camera_node_config,
                charuco_board: calibrationConfig.charucoBoard,
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
