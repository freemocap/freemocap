import {configureStore} from "@reduxjs/toolkit";
import {cameraSlice} from "./slices/cameras/cameras-slice";
import {recordingSlice} from "./slices/recording/recording-slice";
import {themeSlice} from "./slices/theme/theme-slice";
import {videosSlice} from "./slices/videos/videos-slice";
import {settingsSlice} from "./slices/settings/settings-slice";

export const store = configureStore({
    reducer: {
        cameras: cameraSlice.reducer,
        recording: recordingSlice.reducer,
        theme: themeSlice.reducer,
        videos: videosSlice.reducer,
        settings: settingsSlice.reducer,
    }
});
