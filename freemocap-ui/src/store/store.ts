import {configureStore} from "@reduxjs/toolkit";
import {cameraSlice} from "@/store/slices/cameras";
import {recordingSlice} from "@/store/slices/recording";
import {themeSlice} from "@/store/slices/theme";
import {videosSlice} from "@/store/slices/videos";
import {realtimeSlice} from "@/store/slices/realtime";
import {calibrationSlice} from "@/store/slices/calibration/calibration-slice";
import {mocapSlice} from "@/store/slices/mocap/mocap-slice";
import {localeSlice} from "@/store/slices/locale";
import {pipelinesSlice} from "@/store/slices/pipelines/pipelines-slice";

export const store = configureStore({
    reducer: {
        cameras: cameraSlice.reducer,
        recording: recordingSlice.reducer,
        theme: themeSlice.reducer,
        videos: videosSlice.reducer,
        realtime: realtimeSlice.reducer,
        calibration: calibrationSlice.reducer,
        mocap: mocapSlice.reducer,
        locale: localeSlice.reducer,
        pipelines: pipelinesSlice.reducer,
    },
});
