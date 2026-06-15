import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "@/store/types";
import type { PupilLabsState } from "./pupil-labs-types";
import {
    connectPupilLabs,
    disconnectPupilLabs,
    getPupilLabsStatus,
} from "./pupil-labs-thunks";

const initialState: PupilLabsState = {
    isConnected: false,
    isConnecting: false,
    isDisconnecting: false,
    isRecording: false,
    error: null,
};

export const pupilLabsSlice = createSlice({
    name: "pupilLabs",
    initialState,
    reducers: {
        pupilLabsErrorCleared(state) {
            state.error = null;
        },
        pupilLabsRecordingStateChanged(state, action: PayloadAction<boolean>) {
            state.isRecording = action.payload;
        },
    },
    extraReducers: (builder) => {
        // -- Connect --
        builder
            .addCase(connectPupilLabs.pending, (state) => {
                state.isConnecting = true;
                state.error = null;
            })
            .addCase(connectPupilLabs.fulfilled, (state) => {
                state.isConnecting = false;
                state.isConnected = true;
            })
            .addCase(connectPupilLabs.rejected, (state, action) => {
                state.isConnecting = false;
                state.error = action.payload ?? "Failed to connect to Pupil Capture";
            });

        // -- Disconnect --
        builder
            .addCase(disconnectPupilLabs.pending, (state) => {
                state.isDisconnecting = true;
                state.error = null;
            })
            .addCase(disconnectPupilLabs.fulfilled, (state) => {
                state.isDisconnecting = false;
                state.isConnected = false;
                state.isRecording = false;
            })
            .addCase(disconnectPupilLabs.rejected, (state, action) => {
                state.isDisconnecting = false;
                state.error = action.payload ?? "Failed to disconnect from Pupil Capture";
            });

        // -- Status --
        builder
            .addCase(getPupilLabsStatus.fulfilled, (state, action) => {
                state.isConnected = action.payload.connected;
                state.isRecording = action.payload.recording;
            })
            .addCase(getPupilLabsStatus.rejected, (state, action) => {
                state.error = action.payload ?? "Failed to get Pupil Labs status";
            });
    },
});

// -- Selectors --

export const selectPupilLabs = (state: RootState) => state.pupilLabs;
export const selectPupilLabsIsConnected = (state: RootState) =>
    state.pupilLabs.isConnected;
export const selectPupilLabsIsRecording = (state: RootState) =>
    state.pupilLabs.isRecording;

// -- Actions --

export const { pupilLabsErrorCleared, pupilLabsRecordingStateChanged } =
    pupilLabsSlice.actions;

export default pupilLabsSlice.reducer;
