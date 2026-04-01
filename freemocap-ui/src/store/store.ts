import {configureStore} from "@reduxjs/toolkit";
import {cameraSlice} from "@/store/slices/cameras";
import {recordingSlice} from "@/store/slices/recording";
import {themeSlice} from "@/store/slices/theme";
import {videosSlice} from "@/store/slices/videos";
import {pipelineSlice} from "@/store/slices/pipeline";
import {calibrationSlice} from "@/store/slices/calibration/calibration-slice";
import {mocapSlice} from "@/store/slices/mocap/mocap-slice";
import {settingsSlice} from "@/store/slices/settings/settings-slice";
import {localeSlice} from "@/store/slices/locale";

export const store = configureStore({
    reducer: {
        cameras: cameraSlice.reducer,
        recording: recordingSlice.reducer,
        theme: themeSlice.reducer,
        videos: videosSlice.reducer,
        pipeline: pipelineSlice.reducer,
        calibration: calibrationSlice.reducer,
        mocap: mocapSlice.reducer,
        settings: settingsSlice.reducer,
        locale: localeSlice.reducer
    },
});
