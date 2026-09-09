import { useEffect } from "react";
import { useAppDispatch, useAppSelector } from "@/store";
import {
    selectCalibrationDirectoryInfo,
    selectDismissedCalibrationPath,
    selectLoadedCalibration,
} from "@/store/slices/calibration/calibration-slice";
import { loadCalibrationToml } from "@/store/slices/calibration/calibration-thunks";

/**
 * Reactively (re)load the parsed calibration TOML whenever the directory
 * watcher surfaces a new `lastSuccessfulCalibrationTomlPath`. Loads the file
 * through the Electron tRPC endpoint which parses the TOML in the main
 * process and returns structured camera data.
 *
 * Skips reloading a path the user has explicitly dismissed (e.g. via
 * "Clear calibration") until a new calibration is recorded/imported and
 * clears the dismissal.
 */
export function useCalibrationTomlLoader(enabled: boolean) {
    const dispatch = useAppDispatch();
    const directoryInfo = useAppSelector(selectCalibrationDirectoryInfo);
    const loaded = useAppSelector(selectLoadedCalibration);
    const dismissedPath = useAppSelector(selectDismissedCalibrationPath);
    const pending = useAppSelector(state => state.calibration.loadRequestId);
    const error = useAppSelector(state => state.calibration.error);

    const path = directoryInfo?.lastSuccessfulCalibrationTomlPath ?? null;

    useEffect(() => {
        if (!enabled || !path) return;
        if (dismissedPath || loaded || pending || error) return;
        dispatch(loadCalibrationToml({ path }));
    }, [dispatch, enabled, path, loaded, dismissedPath, pending, error]);
}
