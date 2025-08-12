import type {PayloadAction} from '@reduxjs/toolkit'
import {createSlice} from '@reduxjs/toolkit'
import {z} from 'zod'

export const FramerateHistorgramSchema = z.object({
    bin_edges: z.array(z.number()),
    bin_counts: z.array(z.number()),
    bin_densities: z.array(z.number()),
})
export const CurrentFramerateSchema = z.object({
    mean_frame_duration_ms: z.number(),
    mean_frames_per_second: z.number(),
    frame_duration_max: z.number(),
    frame_duration_min: z.number(),
    frame_duration_mean: z.number(),
    frame_duration_stddev: z.number(),
    frame_duration_median: z.number(),
    frame_duration_coefficient_of_variation: z.number(),
    calculation_window_size: z.number(),
    framerate_source: z.string(),
});
export type CurrentFramerate = z.infer<typeof CurrentFramerateSchema>;


// Set a maximum number of framerate entries to store
const MAX_FRAMERATE_ENTRIES = 1000;

interface FramerateState {
    currentFrontendFramerate: z.infer<typeof CurrentFramerateSchema> | null;
    currentBackendFramerate: z.infer<typeof CurrentFramerateSchema> | null;
    recentFrontendFrameDurations: number[]
    recentBackendFrameDurations: number[]
}

const initialState: FramerateState = {
    currentFrontendFramerate: null,
    currentBackendFramerate: null,
    recentFrontendFrameDurations: [],
    recentBackendFrameDurations: [],
}

export const framerateTrackerSlice = createSlice({
    name: 'framerate',
    initialState,
    reducers: {
        setFrontendFramerate: (state, action: PayloadAction<CurrentFramerate>) => {
            state.currentFrontendFramerate = CurrentFramerateSchema.parse(action.payload);

            // Keep a rolling list of recent framerates
            state.recentFrontendFrameDurations.push(state.currentFrontendFramerate.frame_duration_median);
            if (state.recentFrontendFrameDurations.length > MAX_FRAMERATE_ENTRIES) {
                state.recentFrontendFrameDurations.shift();
            }
        },
        setBackendFramerate: (state, action: PayloadAction<CurrentFramerate>) => {
            state.currentBackendFramerate = CurrentFramerateSchema.parse(action.payload);

            // Keep a rolling list of recent framerates
            state.recentBackendFrameDurations.push(state.currentBackendFramerate.frame_duration_median);
            if (state.recentBackendFrameDurations.length > MAX_FRAMERATE_ENTRIES) {
                state.recentBackendFrameDurations.shift();
            }

        },
    }
})

export const {setFrontendFramerate, setBackendFramerate} = framerateTrackerSlice.actions
export default framerateTrackerSlice.reducer
