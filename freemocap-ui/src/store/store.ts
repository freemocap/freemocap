import {configureStore} from "@reduxjs/toolkit";
import {cameraConfigListenerMiddleware} from "@/store/camera-config-listener";
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
import {saveToStorage} from "@/store/persistence";

export const store = configureStore({
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(cameraConfigListenerMiddleware.middleware),
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
    },
});

store.subscribe(() => {
    const s = store.getState();
    saveToStorage('activeRecording', {
        recordingName: s.activeRecording.recordingName,
        baseDirectory: s.activeRecording.baseDirectory,
        layoutPreset: s.activeRecording.layoutPreset,
    });
    saveToStorage('recording.config', s.recording.config);
    saveToStorage('recording.directory', s.recording.recordingDirectory);
    saveToStorage('calibration.config', s.calibration.config);
    saveToStorage('mocap.config', s.mocap.config);
    saveToStorage('blender.settings', {
        blenderExePath: s.blender.blenderExePath,
        exportToBlenderEnabled: s.blender.exportToBlenderEnabled,
        autoOpenBlendFile: s.blender.autoOpenBlendFile,
    });
});
