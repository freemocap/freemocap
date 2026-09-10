import {useEffect} from 'react';
import {useAppDispatch, useAppSelector} from '@/store';
import {restoreCalibrationSelection} from '@/store/slices/calibration';

/** Restore the running selection, or the default when no pipeline is running. This only reads server state. */
export function useCalibrationTomlLoader(enabled: boolean): void {
    const dispatch = useAppDispatch();
    const connected = useAppSelector(state => state.connection.isConnected);
    const {loadedCalibration, dismissedCalibrationPath, loadRequestId, error, mostRecentLoadAttempted} = useAppSelector(state => state.calibration);
    useEffect(() => {
        if (!enabled || !connected || loadedCalibration || dismissedCalibrationPath || loadRequestId || error || mostRecentLoadAttempted) return;
        void dispatch(restoreCalibrationSelection());
    }, [dispatch, enabled, connected, loadedCalibration, dismissedCalibrationPath, loadRequestId, error, mostRecentLoadAttempted]);
}
