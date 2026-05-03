import {RootState} from "@/store";
import {createSelector} from "@reduxjs/toolkit";
import {selectCameras} from "@/store/slices/cameras";

// ==================== Primitive Selectors ====================

export const selectPipelineState = (state: RootState) => state.realtime;
export const selectIsPipelineConnected = (state: RootState) => state.realtime.isConnected;
export const selectPipelineId = (state: RootState) => state.realtime.pipelineId;
export const selectCameraGroupId = (state: RootState) => state.realtime.cameraGroupId;
export const selectIsPipelineLoading = (state: RootState) => state.realtime.isLoading;
export const selectPipelineError = (state: RootState) => state.realtime.error;
export const selectPipelineConfig = (state: RootState) => state.realtime.pipelineConfig;
export const selectCameraNodeConfig = (state: RootState) => state.realtime.pipelineConfig.camera_node_config;
export const selectAggregatorConfig = (state: RootState) => state.realtime.pipelineConfig.aggregator_config;

// ==================== Derived Selectors ====================

export const selectCanConnectPipeline = createSelector(
    [selectIsPipelineConnected, selectIsPipelineLoading, selectCameras],
    (isConnected, isLoading, cameras) => {
        const anyCameraRealtimeEnabled = cameras.some(cam => cam.selected && cam.realtimeEnabled);
        return !isConnected && !isLoading && anyCameraRealtimeEnabled;
    }
);

export const selectCanDisconnectPipeline = createSelector(
    [selectIsPipelineConnected, selectIsPipelineLoading],
    (isConnected, isLoading) => isConnected && !isLoading
);
