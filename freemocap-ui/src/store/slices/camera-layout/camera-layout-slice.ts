import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import type { CalibratedCamera } from "@/services/server/transport/message-contract";

interface CameraLayoutState {
    cameras: CalibratedCamera[];
}

const initialState: CameraLayoutState = { cameras: [] };

export const cameraLayoutSlice = createSlice({
    name: "cameraLayout",
    initialState,
    reducers: {
        camerasReceived: (state, action: PayloadAction<CalibratedCamera[]>) => {
            state.cameras = action.payload;
        },
    },
});

export const { camerasReceived } = cameraLayoutSlice.actions;
