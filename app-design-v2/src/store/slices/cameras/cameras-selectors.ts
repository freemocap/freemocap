import { createSelector } from '@reduxjs/toolkit';
import { RootState } from '../../types';
import { cameraAdapter } from './cameras-adapter';
import { CameraConfig } from './cameras-types';

// Export entity adapter selectors
const adapterSelectors = cameraAdapter.getSelectors<RootState>(
    (state: { cameras: any; }) => state.cameras
);

export const selectAllCameras = adapterSelectors.selectAll;
export const selectCameraById = adapterSelectors.selectById;
export const selectCameraEntities = adapterSelectors.selectEntities;
export const selectCameraCount = adapterSelectors.selectTotal;

// Custom memoized selectors
export const selectSelectedCameras = createSelector(
    [selectAllCameras],
    (cameras) => cameras.filter((camera) => camera.selected)
);

export const selectSelectedCameraConfigs = createSelector(
    [selectSelectedCameras],
    (selectedCameras): Record<string, CameraConfig> => {
        return selectedCameras.reduce(
            (configs, camera) => ({
                ...configs,
                [camera.cameraId]: camera.config,
            }),
            {}
        );
    }
);

export const selectCameraLoadingState = (state: RootState) => state.cameras.isLoading;
export const selectCameraError = (state: RootState) => state.cameras.error;
export const selectCameraConnectionStatus = (state: RootState) =>
    state.cameras.connectionStatus;
