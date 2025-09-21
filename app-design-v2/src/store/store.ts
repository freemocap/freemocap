import {configureStore} from "@reduxjs/toolkit";
import {framerateSlice} from "./slices/framerate/framerate-slice";
import {cameraSlice} from "./slices/cameras/cameras-slice";
import {recordingSlice} from "./slices/recording/recording-slice";
import {connectionSlice} from "@/store/slices/connection/connection-slice.ts";
import {logRecordsSlice} from "./slices/log-records/log-records-slice";

export const store = configureStore({
    reducer: {
        cameras: cameraSlice.reducer,
        recording: recordingSlice.reducer,
        framerate: framerateSlice.reducer,
        logs: logRecordsSlice.reducer,
        server: connectionSlice.reducer,
    }
});


