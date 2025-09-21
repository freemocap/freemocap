import { createEntityAdapter } from '@reduxjs/toolkit';
import { CameraDevice } from './cameras-types';

export const cameraAdapter = createEntityAdapter<CameraDevice, string>({
    selectId: (camera) => camera.cameraId,
    sortComparer: (a, b) => a.index - b.index,
});
