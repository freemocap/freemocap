import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import type { CoordinateConvention } from "@/services/server/transport/message-contract";

interface ConventionState {
    convention: CoordinateConvention | null;
}

const initialState: ConventionState = { convention: null };

export const conventionSlice = createSlice({
    name: "convention",
    initialState,
    reducers: {
        conventionReceived: (state, action: PayloadAction<CoordinateConvention>) => {
            state.convention = action.payload;
        },
    },
});

export const { conventionReceived } = conventionSlice.actions;
