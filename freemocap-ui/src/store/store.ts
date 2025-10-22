import {configureStore} from "@reduxjs/toolkit";
import {framerateSlice} from "./slices/framerate/framerate-slice";
import {cameraSlice} from "./slices/cameras/cameras-slice";
import {recordingSlice} from "./slices/recording/recording-slice";
import {themeSlice} from "./slices/theme/theme-slice";
import {videosSlice} from "./slices/videos/videos-slice";
import {logRecordsSlice} from "./slices/log-records/log-records-slice";
import {pipelineSlice} from "./slices/pipeline/pipeline-slice";

export const store = configureStore({
    reducer: {
        cameras: cameraSlice.reducer,
        recording: recordingSlice.reducer,
        framerate: framerateSlice.reducer,
        logs: logRecordsSlice.reducer,
        theme: themeSlice.reducer,
        videos: videosSlice.reducer,
        pipeline: pipelineSlice.reducer
    }
});


