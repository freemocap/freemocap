import {configureStore} from "@reduxjs/toolkit";
import {cameraConfigListenerMiddleware} from "@/store/camera-config-listener";
import {persistenceListenerMiddleware} from "@/store/persistence-listener";
import {cameraSlice} from "@/store/slices/cameras";
import {recordingSlice} from "@/store/slices/recording";
import {themeSlice} from "@/store/slices/theme";
import {videosSlice} from "@/store/slices/videos";
import {realtimeSlice} from "@/store/slices/realtime";
import {calibrationSlice} from "@/store/slices/calibration/calibration-slice";
import {mocapSlice} from "@/store/slices/mocap/mocap-slice";
import {localeSlice} from "@/store/slices/locale";
import {pipelinesSlice} from "@/store/slices/pipelines/pipelines-slice";
import {blenderSlice} from "@/store/slices/blender/blender-slice";
import {recordingStatusSlice} from "@/store/slices/recording-status/recording-status-slice";
import {activeRecordingSlice} from "@/store/slices/active-recording/active-recording-slice";
import playbackDataReducer from "@/store/slices/playback-data/playback-data-slice";

export const store = configureStore({
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware()
            .concat(cameraConfigListenerMiddleware.middleware)
            .concat(persistenceListenerMiddleware.middleware),
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
        blender: blenderSlice.reducer,
        recordingStatus: recordingStatusSlice.reducer,
        activeRecording: activeRecordingSlice.reducer,
        playbackData: playbackDataReducer,
    },
});
