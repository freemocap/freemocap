// basic selectors
import {RootState} from "@/store";
import {createSelector} from "@reduxjs/toolkit";

export const selectPipelineState = (state: RootState) => state.realtime;
export const selectIsPipelineConnected = (state: RootState) => state.realtime.isConnected;
export const selectPipelineId = (state: RootState) => state.realtime.pipelineId;
export const selectCameraGroupId = (state: RootState) => state.realtime.cameraGroupId;
export const selectIsPipelineLoading = (state: RootState) => state.realtime.isLoading;
export const selectPipelineError = (state: RootState) => state.realtime.error;

// derived selectors
export const selectPipelineInfo = createSelector(
    [selectIsPipelineConnected, selectPipelineId, selectCameraGroupId],
    (isConnected, pipelineId, cameraGroupId) => ({
        isConnected,
        pipelineId,
        cameraGroupId,
    })
);

export const selectCanConnectPipeline = createSelector(
    [selectIsPipelineConnected, selectIsPipelineLoading, (state: RootState) => state.cameras.cameras],
    (isConnected, isLoading, cameras) => {
        const anyCameraSelected = cameras.some(cam => cam.selected);
        return !isConnected && !isLoading && anyCameraSelected;
    }
);

export const selectCanDisconnectPipeline = createSelector(
    [selectIsPipelineConnected, selectIsPipelineLoading],
    (isConnected, isLoading) => isConnected && !isLoading
);
