// cameras-selectors.ts
import {createSelector} from '@reduxjs/toolkit';
import {RootState} from '../../types';
import {CameraConfig} from './cameras-types';

// ========== Basic Selectors ==========
export const selectCameras = (state: RootState) => state.cameras.cameras;
export const selectIsLoading = (state: RootState) => state.cameras.isLoading;
export const selectError = (state: RootState) => state.cameras.error;

// ========== Derived Selectors ==========
export const selectCameraById = createSelector(
    [selectCameras, (_: RootState, cameraId: string) => cameraId],
    (cameras, cameraId) => cameras.find(cam => cam.id === cameraId)
);

export const selectSelectedCameras = createSelector(
    [selectCameras],
    (cameras) => cameras.filter(cam => cam.selected)
);

export const selectConnectedCameras = createSelector(
    [selectCameras],
    (cameras) => cameras.filter(cam => cam.connectionStatus === 'connected')
);

// Get desired configs for selected cameras (for API calls)
export const selectSelectedCameraConfigs = createSelector(
    [selectSelectedCameras],
    (cameras): Record<string, CameraConfig> => {
        return cameras.reduce(
            (configs, camera) => ({
                ...configs,
                [camera.id]: camera.desiredConfig,  // Use desired config
            }),
            {} as Record<string, CameraConfig>
        );
    }
);



// ========== Mismatch Selectors ==========
export const selectCamerasWithConfigMismatch = createSelector(
    [selectCameras],
    (cameras) => cameras.filter(cam => cam.hasConfigMismatch)
);

export const selectHasAnyConfigMismatch = createSelector(
    [selectCamerasWithConfigMismatch],
    (camerasWithMismatch) => camerasWithMismatch.length > 0
);

export const selectCameraHasConfigMismatch = createSelector(
    [selectCameraById],
    (camera) => camera?.hasConfigMismatch ?? false
);

// Get config comparison for a specific camera
export const selectCameraConfigComparison = createSelector(
    [selectCameraById],
    (camera) => {
        if (!camera) return null;

        return {
            actual: camera.actualConfig,
            desired: camera.desiredConfig,
            hasMismatch: camera.hasConfigMismatch,
            differences: camera.hasConfigMismatch ?
                getConfigDifferences(camera.actualConfig, camera.desiredConfig) : []
        };
    }
);

// ========== Count Selectors ==========
export const selectCameraCount = createSelector(
    [selectCameras],
    (cameras) => cameras.length
);

export const selectHasConnectedCameras = createSelector(
    [selectConnectedCameras],
    (cameras) => cameras.length > 0
);

// ========== Helper Functions ==========
function getConfigDifferences(
    actual: CameraConfig,
    desired: CameraConfig
): Array<{ field: string; actual: any; desired: any }> {
    const differences: Array<{ field: string; actual: any; desired: any }> = [];

    // Compare each field
    if (actual.resolution.width !== desired.resolution.width) {
        differences.push({
            field: 'resolution.width',
            actual: actual.resolution.width,
            desired: desired.resolution.width
        });
    }
    if (actual.resolution.height !== desired.resolution.height) {
        differences.push({
            field: 'resolution.height',
            actual: actual.resolution.height,
            desired: desired.resolution.height
        });
    }
    if (actual.framerate !== desired.framerate) {
        differences.push({
            field: 'framerate',
            actual: actual.framerate,
            desired: desired.framerate
        });
    }
    if (actual.exposure_mode !== desired.exposure_mode) {
        differences.push({
            field: 'exposure_mode',
            actual: actual.exposure_mode,
            desired: desired.exposure_mode
        });
    }
    if (actual.exposure !== desired.exposure) {
        differences.push({
            field: 'exposure',
            actual: actual.exposure,
            desired: desired.exposure
        });
    }
    if (actual.rotation !== desired.rotation) {
        differences.push({
            field: 'rotation',
            actual: actual.rotation,
            desired: desired.rotation
        });
    }
    if (actual.pixel_format !== desired.pixel_format) {
        differences.push({
            field: 'pixel_format',
            actual: actual.pixel_format,
            desired: desired.pixel_format
        });
    }
    if (actual.capture_fourcc !== desired.capture_fourcc) {
        differences.push({
            field: 'capture_fourcc',
            actual: actual.capture_fourcc,
            desired: desired.capture_fourcc
        });
    }
    if (actual.writer_fourcc !== desired.writer_fourcc) {
        differences.push({
            field: 'writer_fourcc',
            actual: actual.writer_fourcc,
            desired: desired.writer_fourcc
        });
    }

    return differences;
}
