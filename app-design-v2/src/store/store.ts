import {configureStore} from "@reduxjs/toolkit";
import {framerateSlice} from "./slices/framerate/framerate-slice";
import {cameraSlice} from "./slices/cameras/cameras-slice";
import {recordingSlice} from "./slices/recording/recording-slice";
import {serverSlice} from "./slices/server/server-slice.ts";
import {logRecordsSlice} from "./slices/log-records/log-records-slice";

export const store = configureStore({
    reducer: {
        cameras: cameraSlice.reducer,
        recording: recordingSlice.reducer,
        framerate: framerateSlice.reducer,
        logs: logRecordsSlice.reducer,
        server: serverSlice.reducer,
    }
});


