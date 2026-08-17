import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import type { ModelDefinition } from "@/services/server/transport/message-contract";

interface ModelState {
    models: ModelDefinition[];
}

const initialState: ModelState = { models: [] };

export const modelSlice = createSlice({
    name: "model",
    initialState,
    reducers: {
        modelsReceived: (state, action: PayloadAction<ModelDefinition[]>) => {
            state.models = action.payload;
        },
    },
});

export const { modelsReceived } = modelSlice.actions;
