import { useEffect } from "react";
import { useAppDispatch, useAppSelector } from "@/store";
import {
    selectCalibrationDirectoryInfo,
    selectLoadedCalibration,
} from "@/store/slices/calibration/calibration-slice";
import { loadCalibrationToml } from "@/store/slices/calibration/calibration-thunks";

/**
 * Reactively (re)load the parsed calibration TOML whenever the directory
 * watcher surfaces a new `lastSuccessfulCalibrationTomlPath`. Loads the file
 * through the Electron tRPC endpoint which parses the TOML in the main
 * process and returns structured camera data.
 */
export function useCalibrationTomlLoader() {
    const dispatch = useAppDispatch();
    const directoryInfo = useAppSelector(selectCalibrationDirectoryInfo);
    const loaded = useAppSelector(selectLoadedCalibration);

    const path = directoryInfo?.lastSuccessfulCalibrationTomlPath ?? null;

    useEffect(() => {
        if (!path) return;
        if (loaded && loaded.path === path) return;
        dispatch(loadCalibrationToml({ path }));
    }, [dispatch, path, loaded]);
}
