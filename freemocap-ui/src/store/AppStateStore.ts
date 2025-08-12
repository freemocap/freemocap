// skellycam-ui/src/store/AppStateStore.ts
import {configureStore} from "@reduxjs/toolkit"
import {recordingInfoSlice} from "./slices/recordingInfoSlice"
import {framerateTrackerSlice} from "./slices/framerateTrackerSlice"
import {logRecordsSlice} from "@/store/slices/logRecordsSlice";
import {type TypedUseSelectorHook, useDispatch, useSelector} from "react-redux";
import {camerasSlice} from "@/store/slices/cameras-slices/camerasSlice";
import {themeSlice} from "@/store/slices/themeSlice";
import {videoLoadingSlice} from "@/store/slices/videoLoadingSlice";

export const AppStateStore = configureStore({
    reducer: {
        cameras: camerasSlice.reducer,
        logRecords: logRecordsSlice.reducer,
        recordingStatus: recordingInfoSlice.reducer,
        framerateTracker: framerateTrackerSlice.reducer,
        videoLoading: videoLoadingSlice.reducer,
        theme: themeSlice.reducer,
    },
})

export type RootState = ReturnType<typeof AppStateStore.getState>
export type AppDispatch = typeof AppStateStore.dispatch
export const useAppDispatch = () => useDispatch<AppDispatch>()
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector
