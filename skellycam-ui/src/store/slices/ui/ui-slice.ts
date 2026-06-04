import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { UIState } from './ui-types';

const initialState: UIState = {
    openCameraSettingsId: null,
};

export const uiSlice = createSlice({
    name: 'ui',
    initialState,
    reducers: {
        openCameraSettings: (state, action: PayloadAction<string>) => {
            state.openCameraSettingsId = action.payload;
        },
        closeCameraSettings: (state) => {
            state.openCameraSettingsId = null;
        },
    },
});

export const {
    openCameraSettings,
    closeCameraSettings,
} = uiSlice.actions;
