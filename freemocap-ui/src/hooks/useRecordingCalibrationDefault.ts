import {useEffect} from 'react';
import {useAppDispatch, useAppSelector} from '@/store';
import {loadRecordingCalibrationDefault} from '@/store/slices/calibration';
import {selectMocapRecordingPath} from '@/store/slices/mocap';

export function useRecordingCalibrationDefault(enabled = true): void {
    const dispatch = useAppDispatch();
    const directory = useAppSelector(selectMocapRecordingPath);
    useEffect(() => {
        if (enabled && directory) void dispatch(loadRecordingCalibrationDefault(directory));
        // Keep discovery alive across panel remounts. The thunk deduplicates the
        // recording and ignores results superseded by a recording or user selection.
    }, [dispatch, directory, enabled]);
}
